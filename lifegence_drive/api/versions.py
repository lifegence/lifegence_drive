# Copyright (c) 2026, Lifegence Corporation and Contributors
# See license.txt
"""Earlier versions of files edited in Collabora, modelled on Google Drive.

Collabora merges everyone's changes into one document and saves it often (after 30
seconds idle, every 5 minutes, and on close), so versions are cut per file, not per
person or per save. An editing session starts with the first save after the file has had
no saves for SESSION_GAP, and lasts at most SESSION_MAX. When a new session starts, the
content as it stood (the result of the previous session) is kept as a version, with
everyone who opened the file for editing in that session as its editors.

Like file versions in Google Drive, a version is deleted after KEEP_DAYS or once
KEEP_COUNT newer versions exist, unless it has a name (Google's "Keep forever"); at most
NAMED_MAX versions of a file can have one. Versions count toward the file owner's storage
and are deleted with the file. Only people who can edit a file see or restore its versions.
"""

import os
import shutil
from datetime import timedelta

import frappe
from frappe.utils import get_datetime, now_datetime
from werkzeug.utils import send_file

from lifegence_drive.api.permissions import user_has_permission
from lifegence_drive.utils import STATUS_ACTIVE, get_home_folder, update_file_size
from lifegence_drive.utils.files import FileManager, storage_key

SESSION_GAP = timedelta(minutes=30)
SESSION_MAX = timedelta(hours=2)
RESTORE_QUIET = timedelta(minutes=5)
KEEP_DAYS = 30
KEEP_COUNT = 100
NAMED_MAX = 40

VERSION = "Drive File Version"
SESSION = "Drive File Edit Session"


def _now():
    return now_datetime()


def _people(text):
    return [u for u in (text or "").splitlines() if u]


def _add(text, user):
    people = _people(text)
    if user and user not in people:
        people.append(user)
    return "\n".join(people)


def _is_open(session, now):
    return bool(
        session.started
        and now - get_datetime(session.last_saved) <= SESSION_GAP
        and now - get_datetime(session.started) <= SESSION_MAX
    )


# Storage


def _version_key(file, stamp):
    home = storage_key(get_home_folder(file.team)["file_url"])
    ext = os.path.splitext(file.file_name or "")[1]
    return f"{home}/.versions/{file.name}/{stamp}{ext}"


def _copy(manager, team, src, dst):
    if manager.s3_enabled:
        bucket = manager.get_bucket(team)
        manager.conn.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": src}, Key=dst)
    else:
        target = manager.site_folder / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manager.site_folder / src, target)


def _delete(manager, team, key):
    if manager.s3_enabled:
        try:
            manager.conn.delete_object(Bucket=manager.get_bucket(team), Key=key)
        except manager.s3_errors:
            pass
    else:
        try:
            (manager.site_folder / key).unlink()
        except FileNotFoundError:
            pass


def _keep(file, saved_at, editors, manager):
    """Copy the file's current content into a new version."""
    stamp = get_datetime(saved_at or _now()).strftime("%Y%m%dT%H%M%S%f")
    key = _version_key(file, stamp)
    _copy(manager, file.team, storage_key(file.file_url), key)
    return frappe.get_doc(
        {
            "doctype": VERSION,
            "file": file.name,
            "team": file.team,
            "file_owner": file.owner,
            "saved_at": saved_at,
            "editors": editors,
            "file_size": int(file.file_size or 0),
            "storage_path": key,
        }
    ).insert(ignore_permissions=True)


def _remove(version, manager):
    _delete(manager, version.team, version.storage_path)
    frappe.delete_doc(VERSION, version.name, ignore_permissions=True, force=True)


def prune(file_name, manager=None, now=None):
    """Drop unnamed versions older than KEEP_DAYS or beyond the newest KEEP_COUNT."""
    manager = manager or FileManager()
    now = now or _now()
    unnamed = frappe.get_all(
        VERSION,
        filters={"file": file_name, "label": ["is", "not set"]},
        fields=["name", "team", "storage_path", "saved_at"],
        order_by="saved_at desc, creation desc",
    )
    cutoff = now - timedelta(days=KEEP_DAYS)
    for i, v in enumerate(unnamed):
        if i >= KEEP_COUNT or get_datetime(v.saved_at) < cutoff:
            _remove(v, manager)


def prune_all():
    """Daily: apply the retention rules to every file that has versions."""
    manager = FileManager()
    for file_name in frappe.get_all(VERSION, distinct=True, pluck="file"):
        prune(file_name, manager)


# Hooks from the WOPI host


def note_editor(file, user):
    """Someone opened the file in Collabora with write access (CheckFileInfo)."""
    if not frappe.db.exists(SESSION, file.name):
        frappe.db.savepoint("drive_edit_session")
        try:
            frappe.get_doc({"doctype": SESSION, "file": file.name, "next_editors": user}).insert(ignore_permissions=True)
            return
        except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
            # Someone else opened it at the same moment and created the row
            frappe.db.rollback(save_point="drive_edit_session")
    session = frappe.get_doc(SESSION, file.name, for_update=True)
    if _is_open(session, _now()):
        session.editors = _add(session.editors, user)
    else:
        # Joins the next session, which starts with its first save
        session.next_editors = _add(session.next_editors, user)
    session.save(ignore_permissions=True)


def before_overwrite(file, user, manager):
    """Collabora is about to save new content (PutFile). Keep the old content if this
    save starts a new editing session."""
    now = _now()
    exists = frappe.db.exists(SESSION, file.name)
    session = frappe.get_doc(SESSION, file.name, for_update=True) if exists else None

    if session and _is_open(session, now):
        session.editors = _add(session.editors, user)
        session.last_saved = now
        session.save(ignore_permissions=True)
        return None

    if session and session.started:
        editors = session.editors
        saved_at = session.last_saved
    else:
        # The first edit in Collabora: the content is still what was uploaded
        editors = file.owner
        saved_at = file.modified
    version = _keep(file, saved_at, editors, manager)

    if not session:
        session = frappe.get_doc({"doctype": SESSION, "file": file.name})
    session.started = now
    session.last_saved = now
    session.editors = _add(session.next_editors, user)
    session.next_editors = ""
    session.save(ignore_permissions=True)
    prune(file.name, manager, now)
    return version


def on_file_trash(doc, method=None):
    """Versions go with the file when it is deleted for good."""
    if doc.is_folder or not frappe.db.table_exists(VERSION):
        return
    manager = FileManager()
    for v in frappe.get_all(VERSION, filters={"file": doc.name}, fields=["name", "team", "storage_path"]):
        _remove(v, manager)
    if frappe.db.exists(SESSION, doc.name):
        frappe.delete_doc(SESSION, doc.name, ignore_permissions=True, force=True)


def storage_used(team, user):
    """Bytes of versions that count toward a person's storage in a team."""
    Version, File = frappe.qb.DocType(VERSION), frappe.qb.DocType("File")
    rows = (
        frappe.qb.from_(Version)
        .join(File)
        .on(File.name == Version.file)
        .where((Version.team == team) & (Version.file_owner == user) & (File.status == STATUS_ACTIVE))
        .select(frappe.query_builder.functions.Coalesce(frappe.query_builder.functions.Sum(Version.file_size), 0))
        .run()
    )
    return int(rows[0][0] or 0)


# API, for people who can edit the file


def _editable_file(entity_name):
    file = frappe.get_doc("File", entity_name)
    if file.is_folder or file.status != STATUS_ACTIVE or not user_has_permission(file, "write"):
        raise frappe.PermissionError("Only people who can edit this file can see its versions.")
    return file


def _version_of(version_name):
    version = frappe.get_doc(VERSION, version_name)
    return _editable_file(version.file), version


def _who(text):
    return [{"user": u, "full_name": frappe.utils.get_fullname(u)} for u in _people(text)]


@frappe.whitelist()
def list_versions(entity_name: str):
    """The file's current content and its kept versions, newest first."""
    file = _editable_file(entity_name)
    session = frappe.db.get_value(SESSION, file.name, ["started", "editors"], as_dict=True)
    current = {
        "saved_at": file.modified,
        "editors": _who(session.editors if session and session.started else file.owner),
        "file_size": file.file_size,
    }
    versions = frappe.get_all(
        VERSION,
        filters={"file": file.name},
        fields=["name", "saved_at", "editors", "label", "file_size"],
        order_by="saved_at desc, creation desc",
    )
    for v in versions:
        v.editors = _who(v.editors)
    return {"current": current, "versions": versions}


@frappe.whitelist()
def name_version(version: str, label: str = ""):
    """Name a version to keep it (Google's "Keep forever"), or clear the name."""
    file, doc = _version_of(version)
    label = (label or "").strip()
    if label and not doc.label:
        named = frappe.db.count(VERSION, {"file": file.name, "label": ["is", "set"]})
        if named >= NAMED_MAX:
            frappe.throw(f"A file can have at most {NAMED_MAX} named versions.")
    frappe.db.set_value(VERSION, doc.name, "label", label)
    if not label:
        prune(file.name)
    return label


@frappe.whitelist()
def restore_version(version: str):
    """Make a version the current content. The content it replaces is kept as a version."""
    file, doc = _version_of(version)
    now = _now()
    session = frappe.db.get_value(SESSION, file.name, ["started", "last_saved", "editors"], as_dict=True)
    if session and session.last_saved and now - get_datetime(session.last_saved) < RESTORE_QUIET:
        frappe.throw(
            "Someone is editing this file. Try again when they have finished.", frappe.ValidationError
        )
    manager = FileManager()
    editors = session.editors if session and session.started else file.owner
    _keep(file, file.modified, editors, manager)
    _copy(manager, file.team, doc.storage_path, storage_key(file.file_url))

    delta = int(doc.file_size or 0) - int(file.file_size or 0)
    frappe.db.set_value("File", file.name, {"file_size": doc.file_size, "modified": now}, update_modified=False)
    if delta and file.folder:
        update_file_size(file.folder, delta)
    # The restored content starts fresh: the next edit opens a new session
    if frappe.db.exists(SESSION, file.name):
        frappe.db.set_value(SESSION, file.name, {"started": None, "editors": "", "next_editors": ""})
    prune(file.name, manager, now)
    return {"restored": doc.name, "saved_at": doc.saved_at}


@frappe.whitelist()
def download_version(version: str):
    file, doc = _version_of(version)
    buf = FileManager().get_file(frappe._dict(file_url=doc.storage_path, team=doc.team))
    stamp = get_datetime(doc.saved_at).strftime("%Y%m%d-%H%M")
    base, ext = os.path.splitext(file.file_name)
    # send_file encodes non-ASCII names (RFC 5987), as downloads of the file itself do
    return send_file(
        buf,
        mimetype=file.mime_type or "application/octet-stream",
        as_attachment=True,
        download_name=f"{base} ({stamp}){ext}",
        environ=frappe.request.environ,
    )
