# Copyright (c) 2026, Lifegence Corporation and Contributors
# See license.txt

"""
Moves a site that has upstream Frappe Drive (app "drive") installed over to lifegence_drive.

Only the records that name the app (including the patch log) are changed here. `bench migrate`
then applies the upstream `develop` patches, which convert the data where needed. Run it after
replacing the drive app with lifegence_drive in the bench and before `bench migrate`:

    bench --site <site> migrate-from-drive
"""

import json

import frappe

OLD_APP = "drive"
NEW_APP = "lifegence_drive"

APP_COLUMNS = {
    "Installed Application": "app_name",
    "Module Def": "app_name",
    "Workspace": "app",
    "Desktop Icon": "app",
}


def run():
    for doctype, column in APP_COLUMNS.items():
        if not frappe.db.table_exists(doctype) or not frappe.db.has_column(doctype, column):
            continue
        frappe.db.set_value(doctype, {column: OLD_APP}, column, NEW_APP, update_modified=False)

    # Patches are recorded by module path; without this, the already applied ones would run again
    for patch in frappe.get_all("Patch Log", filters={"patch": ["like", f"{OLD_APP}.patches.%"]}, pluck="patch"):
        renamed = NEW_APP + patch.removeprefix(OLD_APP)
        if frappe.db.exists("Patch Log", {"patch": renamed}):
            frappe.db.delete("Patch Log", {"patch": patch})
        else:
            frappe.db.set_value("Patch Log", {"patch": patch}, "patch", renamed, update_modified=False)

    installed = json.loads(frappe.db.get_global("installed_apps") or "[]")
    if OLD_APP in installed:
        installed = [NEW_APP if app == OLD_APP else app for app in installed]
        frappe.db.set_global("installed_apps", json.dumps(installed))

    frappe.db.commit()
    frappe.clear_cache()
    print(f"Moved {frappe.local.site} from {OLD_APP} to {NEW_APP}. Run `bench --site {frappe.local.site} migrate` next.")
