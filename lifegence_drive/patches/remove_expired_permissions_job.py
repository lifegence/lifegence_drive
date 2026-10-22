import frappe


def execute():
    frappe.db.delete(
        "Scheduled Job Type",
        {"method": "lifegence_drive.api.permissions.auto_delete_expired_perms"},
    )
