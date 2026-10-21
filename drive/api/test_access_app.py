# Copyright (c) 2026, Lifegence Corporation and Contributors
# See license.txt

import frappe
try:
    from frappe.tests import IntegrationTestCase
except ImportError:  # Frappe v15
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from drive.api.product import access_app

USER = "drive-apps-screen@test.io"


class TestAccessApp(IntegrationTestCase):
    def setUp(self):
        if not frappe.db.exists("User", USER):
            frappe.get_doc(doctype="User", email=USER, first_name="Apps", send_welcome_email=0).insert(
                ignore_permissions=True
            )
        self.user = frappe.get_doc("User", USER)
        self.user.remove_roles("System Manager")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.local.conf.pop("drive_app_roles", None)

    def check(self, roles):
        if roles is None:
            frappe.local.conf.pop("drive_app_roles", None)
        else:
            frappe.local.conf.drive_app_roles = roles
        frappe.set_user(USER)
        return access_app()

    def test_everyone_sees_drive_by_default(self):
        self.assertTrue(self.check(None))

    def test_user_without_listed_role_does_not_see_drive(self):
        self.assertFalse(self.check(["System Manager"]))
        self.assertFalse(self.check("System Manager"))

    def test_user_with_listed_role_sees_drive(self):
        self.user.add_roles("System Manager")
        self.assertTrue(self.check(["Drive Admin", "System Manager"]))

    def test_administrator_always_sees_drive(self):
        frappe.local.conf.drive_app_roles = ["System Manager"]
        frappe.set_user("Administrator")
        self.assertTrue(access_app())
