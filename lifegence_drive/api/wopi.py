# Copyright (c) 2026, Lifegence Corporation and Contributors
# See license.txt
"""WOPI host for Collabora Online.

Off unless the site config sets drive_collabora_url (the Collabora server as this
site reaches it). drive_collabora_wopi_base is the base URL that Collabora uses to
reach this site; it defaults to the site URL.

Collabora calls /wopi/files/<file> (CheckFileInfo) and /wopi/files/<file>/contents
(GetFile, PutFile) with an access token that this module signs. Every call checks
Drive permissions again as the token's user.
"""

import base64
import hashlib
import hmac
import json
import os
import shutil
import time
import uuid
from datetime import UTC
from urllib.parse import quote
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import frappe
import requests
from frappe import _
from frappe.utils.password import get_encryption_key
from werkzeug.wrappers import Response

from lifegence_drive.api.permissions import user_has_permission
from lifegence_drive.utils import update_file_size
from lifegence_drive.utils.files import FileManager, storage_key

TOKEN_TTL = 10 * 60 * 60  # seconds; Collabora refreshes the editor before it runs out
DISCOVERY_TTL = 60 * 60


def collabora_url():
    url = frappe.conf.get("drive_collabora_url")
    return url.rstrip("/") if url else None


def wopi_base():
    return (frappe.conf.get("drive_collabora_wopi_base") or frappe.utils.get_url()).rstrip("/")


# Tokens


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: bytes) -> str:
    key = hashlib.sha256(("lifegence_drive.wopi:" + get_encryption_key()).encode()).digest()
    return _b64(hmac.new(key, payload, hashlib.sha256).digest())


def make_token(file: str, user: str, ttl: int = TOKEN_TTL) -> tuple[str, int]:
    expires = int(time.time()) + ttl
    payload = json.dumps({"f": file, "u": user, "e": expires}, separators=(",", ":")).encode()
    return f"{_b64(payload)}.{_sign(payload)}", expires


def read_token(token: str, file: str) -> str | None:
    """Return the token's user if the token is valid for this file, else None."""
    try:
        body, sig = token.split(".", 1)
        payload = _unb64(body)
    except (ValueError, TypeError):
        return None
    if not hmac.compare_digest(sig, _sign(payload)):
        return None
    data = json.loads(payload)
    if data.get("f") != file or data.get("e", 0) < time.time():
        return None
    return data.get("u")


# Discovery


def discovery() -> dict[str, dict[str, str]]:
    """{extension: {action: urlsrc}} from Collabora's discovery XML, cached for an hour."""
    cached = frappe.cache.get_value("lifegence_drive:collabora_discovery")
    if cached:
        return cached
    xml = requests.get(f"{collabora_url()}/hosting/discovery", timeout=10).text
    actions = {}
    for action in ElementTree.fromstring(xml).iter("action"):
        if action.get("ext"):
            actions.setdefault(action.get("ext"), {})[action.get("name")] = action.get("urlsrc")
    frappe.cache.set_value("lifegence_drive:collabora_discovery", actions, expires_in_sec=DISCOVERY_TTL)
    return actions


def extension(file_name: str) -> str:
    return os.path.splitext(file_name)[1].lstrip(".").lower()


@frappe.whitelist()
def get_editor(entity_name: str):
    """Where and how the browser opens a file in Collabora."""
    if not collabora_url():
        frappe.throw("Collabora is not configured on this site.")
    if not user_has_permission(entity_name, "read"):
        raise frappe.PermissionError("You do not have permission to view this file")
    file_name = frappe.db.get_value("File", entity_name, "file_name")
    actions = discovery().get(extension(file_name)) or {}
    can_write = bool(user_has_permission(entity_name, "write"))
    urlsrc = actions.get("edit" if can_write else "view") or actions.get("view")
    if not urlsrc:
        frappe.throw("This file type can't be opened in Collabora.")
    token, expires = make_token(entity_name, frappe.session.user)
    wopi_src = f"{wopi_base()}/wopi/files/{entity_name}"
    sep = "" if urlsrc.endswith(("?", "&")) else ("&" if "?" in urlsrc else "?")
    lang = (frappe.local.lang or "en").replace("_", "-")
    return {
        "action_url": f"{urlsrc}{sep}WOPISrc={quote(wopi_src, safe='')}&lang={lang}",
        "access_token": token,
        "access_token_ttl": expires * 1000,
        "can_write": can_write,
        "file_name": file_name,
    }


@frappe.whitelist(allow_guest=True)
def settings():
    """What the frontend needs to offer Collabora: whether it's on and which extensions it edits."""
    if not collabora_url():
        return {"enabled": False, "extensions": []}
    try:
        exts = sorted(ext for ext, actions in discovery().items() if "edit" in actions)
    except Exception:
        frappe.log_error("Drive: could not read Collabora discovery")
        return {"enabled": False, "extensions": []}
    return {"enabled": True, "extensions": exts}


@frappe.whitelist()
def preview_pdf(entity_name: str):
    """Render an Office file as PDF with Collabora, so previews stay on our servers."""
    if not collabora_url():
        frappe.throw(_("Collabora is not configured on this site."))
    if not user_has_permission(entity_name, "read"):
        raise frappe.PermissionError(_("You do not have permission to view this file"))
    file = frappe.get_doc("File", entity_name)
    # The language picks the fonts for CJK text (without it, kanji fall back to Chinese fonts)
    lang = (frappe.local.lang or "en").replace("_", "-")
    cache_key = f"lifegence_drive:collabora_pdf:{file.name}:{file.modified}:{lang}"
    pdf = frappe.cache.get_value(cache_key)
    if not pdf:
        data = FileManager().get_file(file).read()
        r = requests.post(
            f"{collabora_url()}/cool/convert-to/pdf",
            files={"data": (file.file_name, data)},
            data={"lang": lang},
            timeout=120,
        )
        if r.status_code != 200:
            frappe.throw(_("The preview could not be generated."))
        pdf = r.content
        frappe.cache.set_value(cache_key, pdf, expires_in_sec=6 * 60 * 60)
    # Frappe mangles non-ASCII names in this header, and the name is never shown
    frappe.local.response.filename = "preview.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "pdf"
    frappe.local.response.display_content_as = "inline"


# WOPI endpoints, served through the page_renderer hook


def _json(data, status=200):
    return Response(json.dumps(data), status=status, mimetype="application/json")


def _iso(dt) -> str:
    """WOPI wants UTC; Frappe stores naive datetimes in the system time zone."""
    dt = frappe.utils.get_datetime(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(frappe.utils.get_system_timezone()))
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def check_file_info(file):
    user = frappe.session.user
    return _json(
        {
            "BaseFileName": file.file_name,
            "Size": int(file.file_size or 0),
            "OwnerId": file.owner,
            "UserId": user,
            "UserFriendlyName": frappe.utils.get_fullname(user),
            "UserCanWrite": bool(user_has_permission(file, "write")),
            "UserCanNotWriteRelative": True,
            "SupportsUpdate": True,
            "SupportsLocks": False,
            "LastModifiedTime": _iso(file.modified),
            "Version": str(file.modified),
            "PostMessageOrigin": frappe.utils.get_url(),
        }
    )


def get_file(file):
    buf = FileManager().get_file(file)
    return Response(buf.read(), mimetype="application/octet-stream")


def put_file(file, request):
    if not user_has_permission(file, "write"):
        return Response(status=401)
    # Collabora sends the modified time it last saw; refuse to overwrite a newer file
    seen = request.headers.get("X-COOL-WOPI-Timestamp")
    if seen and seen != _iso(file.modified):
        return _json({"COOLStatusCode": 1010}, status=409)

    content = request.get_data()
    manager = FileManager()
    root = frappe.get_single("Drive Disk Settings").root_folder or ""
    uploads = os.path.join(frappe.get_site_path("private/files"), root, ".uploads")
    os.makedirs(uploads, exist_ok=True)
    temp_path = os.path.join(uploads, f"{uuid.uuid4().hex}_wopi")
    with open(temp_path, "wb") as f:
        f.write(content)

    if not manager.s3_enabled:
        # PoC: keep the previous content next to the uploads folder
        backup_dir = os.path.join(uploads, "..", ".collabora-backup")
        os.makedirs(backup_dir, exist_ok=True)
        current = manager.site_folder / storage_key(file.file_url)
        if current.exists():
            shutil.copy2(current, os.path.join(backup_dir, f"{file.name}-{int(time.time())}"))

    from pathlib import Path

    manager.upload_file(Path(temp_path), file, create_thumbnail=False)
    delta = len(content) - int(file.file_size or 0)
    now = frappe.utils.now_datetime()
    frappe.db.set_value(
        "File", file.name, {"file_size": len(content), "modified": now, "file_modified": now}, update_modified=False
    )
    if delta and file.folder:
        try:
            update_file_size(file.folder, delta)
        except Exception:
            pass
    return _json({"LastModifiedTime": _iso(now)})


def authenticate():
    """auth_hooks entry: Collabora also sends the access token as a Bearer header,
    which Frappe would otherwise reject as an unknown OAuth token."""
    request = getattr(frappe.local, "request", None)
    if not request or not collabora_url():
        return
    parts = request.path.strip("/").split("/")
    if len(parts) < 3 or parts[:2] != ["wopi", "files"]:
        return
    token = request.args.get("access_token", "")
    header = request.headers.get("Authorization", "")
    if not token and header.lower().startswith("bearer "):
        token = header[7:]
    user = read_token(token, parts[2])
    if user and frappe.db.exists("User", {"name": user, "enabled": 1}):
        frappe.set_user(user)


class WOPIPage:
    """page_renderer for /wopi/files/<file>[/contents]."""

    def __init__(self, path=None, http_status_code=None):
        self.path = (path or frappe.local.request.path).strip("/")

    def can_render(self):
        return bool(collabora_url()) and self.path.startswith("wopi/files/")

    def render(self):
        request = frappe.local.request
        parts = self.path.split("/")
        if len(parts) not in (3, 4) or (len(parts) == 4 and parts[3] != "contents"):
            return Response(status=404)
        name = parts[2]
        user = read_token(request.args.get("access_token", ""), name)
        if not user or not frappe.db.exists("User", {"name": user, "enabled": 1}):
            return Response(status=401)
        frappe.set_user(user)
        file = frappe.db.get_value(
            "File",
            {"name": name, "is_folder": 0},
            ["name", "file_name", "file_size", "file_url", "owner", "modified", "folder", "team"],
            as_dict=True,
        )
        if not file:
            return Response(status=404)
        doc = frappe.get_doc("File", name)
        if not user_has_permission(doc, "read"):
            return Response(status=401)
        if len(parts) == 3:
            return check_file_info(doc) if request.method == "GET" else Response(status=501)
        if request.method == "GET":
            return get_file(doc)
        if request.method == "POST" and request.headers.get("X-WOPI-Override") == "PUT":
            return put_file(doc, request)
        return Response(status=501)
