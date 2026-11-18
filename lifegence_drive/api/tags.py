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
from frappe.query_builder import functions as fn

from lifegence_drive.utils import STATUS_ACTIVE
from .permissions import get_teams, user_has_permission

MAX_TAG_LENGTH = 140

DriveFile = frappe.qb.DocType("File")
TagLink = frappe.qb.DocType("Tag Link")


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


def _set_tags(doc, tags: list[str]):
    """Write `_user_tags` and keep `Tag Link` rows in step, like DocTags.update."""
    unique, seen = [], set()
    for tag in tags:
        if tag.lower() not in seen:
            seen.add(tag.lower())
            unique.append(tag)

    for tag in unique:
        if not frappe.db.exists("Tag", tag):
            frappe.get_doc({"doctype": "Tag", "name": tag}).insert(ignore_permissions=True)

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
        current = parse_tags(frappe.db.get_value("File", doc.name, "_user_tags"))
        if tag.lower() in (t.lower() for t in current):
            result[doc.name] = current
        else:
            result[doc.name] = _set_tags(doc, current + [tag])
    return result


@frappe.whitelist(methods=["POST"])
def remove_tag(entity_names: list[str] | str, tag: str) -> dict:
    """Remove a tag (case-insensitive) from one or more files."""
    tag = " ".join((tag or "").split())
    docs = [_get_entity(name, "write") for name in _as_list(entity_names)]
    result = {}
    for doc in docs:
        current = parse_tags(frappe.db.get_value("File", doc.name, "_user_tags"))
        result[doc.name] = _set_tags(doc, [t for t in current if t.lower() != tag.lower()])
    return result


@frappe.whitelist()
def get_tags(team: str | None = None, txt: str | None = None) -> list[dict]:
    """
    Tags in use on active files of the user's teams, with how many files carry each.
    Pass `team` to limit to one team and `txt` to filter by substring.
    """
    teams = get_teams()
    if team and team != "all":
        teams = [t for t in teams if t == team]
    if not teams:
        return []

    query = (
        frappe.qb.from_(TagLink)
        .join(DriveFile)
        .on(DriveFile.name == TagLink.document_name)
        .where(
            (TagLink.document_type == "File")
            & (DriveFile.team.isin(teams))
            & (DriveFile.status == STATUS_ACTIVE)
        )
        .groupby(TagLink.tag)
        .select(TagLink.tag, fn.Count("*").as_("count"))
        .orderby(TagLink.tag)
    )
    if txt:
        query = query.where(TagLink.tag.like(f"%{txt}%"))
    return query.run(as_dict=True)
