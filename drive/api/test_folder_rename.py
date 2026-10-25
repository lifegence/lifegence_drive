# Copyright (c) 2026, Lifegence Corporation and Contributors
# See license.txt

import os

import frappe

try:
    from frappe.tests import IntegrationTestCase
except ImportError:  # Frappe v15
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from drive.api.files import call_controller_method, create_folder

OWNER = "drive-rename-owner@test.io"
EDITOR = "drive-rename-editor@test.io"


def make_user(email):
    if not frappe.db.exists("User", email):
        # No roles: like an outside collaborator who only reaches files through Drive sharing
        frappe.get_doc(
            doctype="User", email=email, first_name=email.split("@")[0], send_welcome_email=0
        ).insert(ignore_permissions=True)


def call(entity_name, method, **kwargs):
    frappe.local.form_dict = frappe._dict(cmd="x", entity_name=entity_name, method=method, **kwargs)
    return call_controller_method()


def on_disk(path):
    return os.path.exists(frappe.get_site_path("private", "files", path))


class TestFolderRename(IntegrationTestCase):
    def setUp(self):
        frappe.db.set_single_value("Drive Disk Settings", "flat", 0)
        make_user(OWNER)
        make_user(EDITOR)
        frappe.set_user(OWNER)
        suffix = frappe.generate_hash(length=8)
        team = frappe.get_doc({"doctype": "Drive Team", "title": f"Rename Test {suffix}"}).insert(
            ignore_permissions=True
        )
        self.top = create_folder(team.name, "Shared")
        self.folder = create_folder(team.name, "Designs", self.top.name)
        self.inner = create_folder(team.name, "Drafts", self.folder.name)
        call(self.top.name, "share", user=EDITOR, read=1, upload=1, write=1)

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.local.form_dict = frappe._dict()

    def test_renaming_a_folder_updates_what_is_inside(self):
        frappe.set_user(EDITOR)
        call(self.folder.name, "rename", new_title="Designs v1")
        inner = frappe.get_doc("Drive File", self.inner.name)
        self.assertIn("Designs v1", inner.path)
        self.assertTrue(on_disk(inner.path), inner.path)
