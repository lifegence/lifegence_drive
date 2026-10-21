# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from drive.api.files import call_controller_method, create_folder

OWNER = "drive-owner@test.io"
OTHER = "drive-other@test.io"


def make_user(email):
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            doctype="User", email=email, first_name=email.split("@")[0], send_welcome_email=0
        ).insert(ignore_permissions=True)


def call(entity_name, method, **kwargs):
    frappe.local.form_dict = frappe._dict(cmd="x", entity_name=entity_name, method=method, **kwargs)
    return call_controller_method()


class TestCallControllerMethod(IntegrationTestCase):
    def setUp(self):
        make_user(OWNER)
        make_user(OTHER)
        frappe.set_user(OWNER)
        # Folders live on disk too, which the test rollback doesn't undo, so keep names unique
        suffix = frappe.generate_hash(length=8)
        team = frappe.get_doc({"doctype": "Drive Team", "title": f"Authz Test {suffix}"}).insert(
            ignore_permissions=True
        )
        self.folder = create_folder(team.name, "Private folder")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.local.form_dict = frappe._dict()

    def test_methods_outside_the_allowlist_are_refused(self):
        for method in ("db_set", "save", "delete", "move", "permanent_delete", "recursive_path_move"):
            with self.subTest(method=method), self.assertRaises(frappe.PermissionError):
                call(self.folder.name, method)

    def test_owner_can_rename(self):
        call(self.folder.name, "rename", new_title="Renamed by owner")
        self.assertEqual(frappe.db.get_value("Drive File", self.folder.name, "title"), "Renamed by owner")

    def test_user_without_access_cannot_rename_or_recolor(self):
        frappe.set_user(OTHER)
        with self.assertRaises(frappe.PermissionError):
            call(self.folder.name, "rename", new_title="Renamed by other")
        with self.assertRaises(frappe.PermissionError):
            call(self.folder.name, "change_color", new_color="#ff0000")
        self.assertEqual(frappe.db.get_value("Drive File", self.folder.name, "title"), "Private folder")

    def test_user_without_access_cannot_share_or_unshare(self):
        frappe.set_user(OTHER)
        with self.assertRaises(frappe.PermissionError):
            call(self.folder.name, "share", user=OTHER, read=1, write=1)
        with self.assertRaises(frappe.PermissionError):
            call(self.folder.name, "unshare", user="$GENERAL")
        self.assertFalse(frappe.db.exists("Drive Permission", {"entity": self.folder.name, "user": OTHER}))

    def test_reader_cannot_rename_but_can_leave(self):
        call(self.folder.name, "share", user=OTHER, read=1)
        frappe.set_user(OTHER)
        with self.assertRaises(frappe.PermissionError):
            call(self.folder.name, "rename", new_title="Renamed by reader")
        call(self.folder.name, "unshare", user=OTHER)
        self.assertFalse(frappe.db.exists("Drive Permission", {"entity": self.folder.name, "user": OTHER}))

    def test_missing_entity_is_rejected(self):
        with self.assertRaises(ValueError):
            call("does-not-exist", "rename", new_title="x")
