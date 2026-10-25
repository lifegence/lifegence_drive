# Copyright (c) 2026, Lifegence Corporation and Contributors
# See license.txt

import os

import frappe

try:
    from frappe.tests import IntegrationTestCase
except ImportError:  # Frappe v15
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from lifegence_drive.api.files import create_folder, move, remove_or_restore, rename, share
from lifegence_drive.utils.files import storage_key

OWNER = "drive-rename-owner@test.io"
EDITOR = "drive-rename-editor@test.io"


def make_user(email):
    if not frappe.db.exists("User", email):
        # No roles: like an outside collaborator who only reaches files through Drive sharing
        frappe.get_doc(
            doctype="User", email=email, first_name=email.split("@")[0], send_welcome_email=0
        ).insert(ignore_permissions=True)


def on_disk(file_url):
    return os.path.exists(frappe.get_site_path(storage_key(file_url)))


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
        share(self.top.name, user=EDITOR, read=1, upload=1, write=1)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_renaming_a_folder_updates_what_is_inside(self):
        frappe.set_user(EDITOR)
        rename(self.folder.name, "Designs v1")
        inner = frappe.get_doc("File", self.inner.name)
        self.assertIn("Designs v1", inner.file_url)
        self.assertTrue(on_disk(inner.file_url), inner.file_url)

    def test_deleting_a_folder_forever_removes_what_is_inside(self):
        frappe.set_user(EDITOR)
        frappe.get_doc("File", self.folder.name).permanent_delete()
        status = frappe.db.get_value("File", self.inner.name, "status")
        self.assertEqual(status, frappe.db.get_value("File", self.folder.name, "status"))

    def test_trash_and_restore_a_shared_folder(self):
        frappe.set_user(EDITOR)
        remove_or_restore([self.folder.name])
        self.assertEqual(frappe.db.get_value("File", self.folder.name, "status"), "Trashed")
        remove_or_restore([self.folder.name])
        self.assertEqual(frappe.db.get_value("File", self.folder.name, "status"), "Active")

    def test_moving_a_folder_updates_what_is_inside(self):
        frappe.set_user(OWNER)
        target = create_folder(frappe.db.get_value("File", self.top.name, "team"), "Archive", self.top.name)
        frappe.set_user(EDITOR)
        move([self.folder.name], new_parent=target.name)
        inner = frappe.get_doc("File", self.inner.name)
        self.assertIn("Archive", inner.file_url)
        self.assertTrue(on_disk(inner.file_url), inner.file_url)

    def upload(self, parent, name, data):
        from io import BytesIO
        from unittest.mock import patch

        from werkzeug.datastructures import FileStorage

        from lifegence_drive.api.files import upload_file

        req = frappe._dict(files={"file": FileStorage(stream=BytesIO(data), filename=name)})
        uuid = frappe.generate_hash(length=8)
        with patch.object(frappe, "request", req, create=True), patch.dict(frappe.form_dict, {"uuid": uuid}, clear=True):
            return upload_file(frappe.db.get_value("File", parent, "team"), len(data), parent=parent)

    def test_upload_into_a_shared_folder(self):
        frappe.set_user(EDITOR)
        doc = self.upload(self.folder.name, "メモ.txt", b"shared upload")
        self.assertEqual(doc.folder, self.folder.name)
        self.assertEqual(doc.owner, EDITOR)

    def test_rename_and_move_keep_file_urls_in_the_stored_form(self):
        frappe.set_user(EDITOR)
        rename(self.folder.name, "Designs v1")
        target = create_folder(frappe.db.get_value("File", self.top.name, "team"), "Archive", self.top.name)
        move([self.inner.name], new_parent=target.name)
        for name in (self.folder.name, self.inner.name):
            url = frappe.db.get_value("File", name, "file_url")
            self.assertTrue(url.startswith("/private/files/"), url)
            self.assertTrue(on_disk(url), url)

    def test_rename_again_after_an_upload(self):
        # A renamed folder used to keep its file_url without the leading slash, while new
        # uploads in it had one, so renaming it again failed on the mismatch
        frappe.set_user(EDITOR)
        rename(self.folder.name, "Designs v1")
        doc = self.upload(self.folder.name, "週報.txt", b"weekly")
        rename(self.folder.name, "Designs v2")
        url = frappe.db.get_value("File", doc.name, "file_url")
        self.assertIn("/Designs v2/", url)
        self.assertTrue(url.startswith("/private/files/"), url)
        self.assertTrue(on_disk(url), url)
