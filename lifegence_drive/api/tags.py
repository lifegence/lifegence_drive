"""Tags for Drive files and folders.

Tags are Frappe's standard tags (`Tag` / `Tag Link` and the `_user_tags`
column on `File`), so they show up in Desk filters and global search too.
They are shared across the site, not per user.

Frappe's own tag API checks Desk permissions on `File`, which Drive users
normally do not have; these endpoints check Drive access instead and then
write the same records.
"""

import frappe
from frappe import _

from lifegence_drive.utils import STATUS_ACTIVE
from .permissions import get_teams, get_user_access, user_has_permission

MAX_TAG_LENGTH = 140


def normalize_tag(tag: str) -> str:
    """Trim, collapse whitespace and reject values that can't be stored as a tag."""
    tag = " ".join((tag or "").split())
    if not tag:
        frappe.throw(_("Tag cannot be empty"), ValueError)
    if "," in tag:
        frappe.throw(_("Tags cannot contain commas"), ValueError)
    if len(tag) > MAX_TAG_LENGTH:
        frappe.throw(_("Tags can be at most {0} characters").format(MAX_TAG_LENGTH), ValueError)
    return tag


def parse_tags(value: str | None) -> list[str]:
    """Split a `_user_tags` value ("a,b", sometimes with a leading comma) into a list."""
    return [t for t in (value or "").split(",") if t]


def _as_list(value) -> list[str]:
    if isinstance(value, str):
        value = frappe.parse_json(value) if value.startswith("[") else [value]
    return list(value or [])


def _get_entity(entity_name: str, ptype: str):
    doc = frappe.get_doc("File", entity_name)
    if not user_has_permission(doc, ptype):
        frappe.throw(_("You don't have access to this file."), frappe.PermissionError)
    return doc


def _locked_tags(name: str) -> list[str]:
    """Read a file's tags and lock its row until the request commits, so concurrent edits queue up."""
    return parse_tags(frappe.db.get_value("File", name, "_user_tags", for_update=True))


def _set_tags(doc, tags: list[str], new_tag: str | None = None):
    """
    Write `_user_tags` and keep `Tag Link` rows in step, like DocTags.update.

    DocTags itself can't be used: its update_tags() calls doc.check_permission("write"),
    i.e. Desk permission on File, which Drive users usually lack. Access has already been
    checked against Drive permissions by the caller. The stored format ("a,b") matches DocTags.
    """
    unique, seen = [], set()
    for tag in tags:
        if tag.lower() not in seen:
            seen.add(tag.lower())
            unique.append(tag)

    if new_tag and not frappe.db.exists("Tag", new_tag):
        frappe.get_doc({"doctype": "Tag", "name": new_tag}).insert(ignore_permissions=True)

    # Same format DocTags.update writes ("a,b"), so Desk tag filters keep working
    value = ",".join(unique)
    frappe.db.set_value("File", doc.name, "_user_tags", value, update_modified=False)

    existing = frappe.get_all(
        "Tag Link", filters={"document_type": "File", "document_name": doc.name}, pluck="tag"
    )
    for tag in set(unique) - set(existing):
        frappe.get_doc(
            {
                "doctype": "Tag Link",
                "document_type": "File",
                "document_name": doc.name,
                "title": doc.file_name or "",
                "tag": tag,
            }
        ).insert(ignore_permissions=True)
    removed = list(set(existing) - set(unique))
    if removed:
        frappe.db.delete(
            "Tag Link", {"document_type": "File", "document_name": doc.name, "tag": ["in", removed]}
        )
    return unique


@frappe.whitelist()
def get_entity_tags(entity_name: str) -> list[str]:
    """Tags on one file or folder."""
    doc = _get_entity(entity_name, "read")
    return parse_tags(frappe.db.get_value("File", doc.name, "_user_tags"))


@frappe.whitelist(methods=["POST"])
def add_tag(entity_names: list[str] | str, tag: str) -> dict:
    """Add a tag to one or more files. Needs edit access to every file."""
    tag = normalize_tag(tag)
    docs = [_get_entity(name, "write") for name in _as_list(entity_names)]
    result = {}
    for doc in docs:
        current = _locked_tags(doc.name)
        if tag.lower() in (t.lower() for t in current):
            result[doc.name] = current
        else:
            result[doc.name] = _set_tags(doc, current + [tag], new_tag=tag)
    return result


@frappe.whitelist(methods=["POST"])
def remove_tag(entity_names: list[str] | str, tag: str) -> dict:
    """Remove a tag (case-insensitive) from one or more files."""
    tag = " ".join((tag or "").split())
    docs = [_get_entity(name, "write") for name in _as_list(entity_names)]
    result = {}
    for doc in docs:
        current = _locked_tags(doc.name)
        kept = [t for t in current if t.lower() != tag.lower()]
        result[doc.name] = _set_tags(doc, kept) if len(kept) != len(current) else current
    return result


@frappe.whitelist()
def get_tags(team: str | None = None, txt: str | None = None) -> list[dict]:
    """
    Tags in use on active files of the user's teams, with how many of those files the
    user can read (the same files `list.tagged` shows). Pass `team` to limit to one team
    and `txt` to filter by substring.
    """
    teams = get_teams()
    if team and team != "all":
        teams = [t for t in teams if t == team]
    if not teams:
        return []

    DriveFile = frappe.qb.DocType("File")
    TagLink = frappe.qb.DocType("Tag Link")
    query = (
        frappe.qb.from_(TagLink)
        .join(DriveFile)
        .on(DriveFile.name == TagLink.document_name)
        .where(
            (TagLink.document_type == "File")
            & (DriveFile.team.isin(teams))
            & (DriveFile.status == STATUS_ACTIVE)
        )
        .select(TagLink.tag, TagLink.document_name)
    )
    if txt:
        escaped = txt.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(TagLink.tag.like(f"%{escaped}%"))

    rows = query.run(as_dict=True)
    # Team membership alone doesn't grant read on every file (explicit read=0 shares)
    readable = {
        name for name in {r.document_name for r in rows} if get_user_access(name).get("read")
    }
    counts = {}
    for r in rows:
        if r.document_name in readable:
            counts[r.tag] = counts.get(r.tag, 0) + 1
    return [{"tag": tag, "count": counts[tag]} for tag in sorted(counts)]
