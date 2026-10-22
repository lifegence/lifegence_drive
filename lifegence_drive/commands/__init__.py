import click
import frappe
from frappe.commands import pass_context
from frappe.exceptions import SiteNotSpecifiedError


@click.command("migrate-from-drive")
@pass_context
def migrate_from_drive(context):
    "Move a site from the app `drive` (upstream Frappe Drive) to lifegence_drive, keeping its data"
    from lifegence_drive.migrate_from_drive import run

    if not context.sites:
        raise SiteNotSpecifiedError
    for site in context.sites:
        frappe.init(site)
        frappe.connect()
        try:
            run()
        finally:
            frappe.destroy()


commands = [migrate_from_drive]
