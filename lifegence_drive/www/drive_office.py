# Copyright (c) 2026, Lifegence Corporation and Contributors
# See license.txt
"""Opens a Drive file in Collabora Online: /drive_office?file=<File name>."""

import frappe

from lifegence_drive.api.wopi import get_editor

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=" + frappe.utils.quote(frappe.request.full_path)
        raise frappe.Redirect
    file = frappe.form_dict.get("file")
    if not file:
        raise frappe.PageDoesNotExistError
    context.view = frappe.utils.cint(frappe.form_dict.get("view"))
    context.editor = get_editor(file, view=context.view)
    context.back_url = "/drive/"
    context.no_header = True
    context.no_breadcrumbs = True
    return context
