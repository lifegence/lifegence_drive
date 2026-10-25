# Copyright (c) 2026, Lifegence Corporation and Contributors
# See license.txt

from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.utils import now_datetime
from werkzeug.datastructures import FileStorage

try:
    from frappe.tests import IntegrationTestCase
except ImportError:  # Frappe v15
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from lifegence_drive.api import versions, wopi
from lifegence_drive.api.files import create_folder, share, upload_file
from lifegence_drive.api.storage import storage_usage
from lifegence_drive.utils.files import FileManager

OWNER = "drive-version-owner@test.io"
EDITOR = "drive-version-editor@test.io"
READER = "drive-version-reader@test.io"


def make_user(email):
    if not frappe.db.exists("User", email):
        # No roles: like an outside collaborator who only reaches files through Drive sharing
        frappe.get_doc(
            doctype="User", email=email, first_name=email.split("@")[0], send_welcome_email=0
        ).insert(ignore_permissions=True)


def content(name):
    return FileManager().get_file(frappe.get_doc("File", name)).read()


def kept(name):
    return frappe.get_all(
        versions.VERSION, filters={"file": name}, fields=["*"], order_by="saved_at asc, creation asc"
    )


def stored(version):
    return FileManager().get_file(frappe._dict(file_url=version.storage_path, team=version.team)).read()


class TestVersions(IntegrationTestCase):
    def setUp(self):
        frappe.db.set_single_value("Drive Disk Settings", "flat", 0)
        for user in (OWNER, EDITOR, READER):
            make_user(user)
        frappe.set_user(OWNER)
        suffix = frappe.generate_hash(length=8)
        self.team = frappe.get_doc({"doctype": "Drive Team", "title": f"Version Test {suffix}"}).insert(
            ignore_permissions=True
        ).name
        self.folder = create_folder(self.team, "Shared")
        share(self.folder.name, user=EDITOR, read=1, upload=1, write=1)
        share(self.folder.name, user=READER, read=1)
        self.file = self.upload("議事録.docx", b"v0")
        self.t0 = now_datetime()

    def tearDown(self):
        frappe.set_user("Administrator")

    def upload(self, name, data):
        req = frappe._dict(files={"file": FileStorage(stream=BytesIO(data), filename=name)})
        with patch.object(frappe, "request", req, create=True), patch.dict(
            frappe.form_dict, {"uuid": frappe.generate_hash(length=8)}, clear=True
        ):
            return upload_file(self.team, len(data), parent=self.folder.name).name

    def at(self, minutes):
        return patch.object(versions, "_now", return_value=self.t0 + timedelta(minutes=minutes))

    def join(self, user, minutes):
        """Collabora's CheckFileInfo for someone opening the file."""
        frappe.set_user(user)
        with self.at(minutes):
            wopi.check_file_info(frappe.get_doc("File", self.file))

    def save(self, user, data, minutes):
        """Collabora's PutFile with the session's new content."""
        frappe.set_user(user)
        with self.at(minutes):
            res = wopi.put_file(frappe.get_doc("File", self.file), SimpleNamespace(headers={}, get_data=lambda: data))
        self.assertEqual(res.status_code, 200, res.get_data())

    def test_first_save_keeps_the_uploaded_content(self):
        self.join(OWNER, 0)
        self.save(OWNER, b"v1", 0)
        [v] = kept(self.file)
        self.assertEqual(stored(v), b"v0")
        self.assertEqual(versions._people(v.editors), [OWNER])
        self.assertEqual(content(self.file), b"v1")

    def test_saves_in_one_session_make_one_version(self):
        # Autosaves every 5 minutes while someone is editing
        for i, minute in enumerate(range(0, 30, 5)):
            self.save(OWNER, f"v{i + 1}".encode(), minute)
        self.assertEqual(len(kept(self.file)), 1)

    def test_co_editors_are_recorded_on_the_version(self):
        self.join(OWNER, 0)
        self.join(EDITOR, 1)
        self.save(OWNER, b"owner edit", 2)
        self.save(EDITOR, b"owner and editor edit", 6)
        # The next session starts after 30 quiet minutes; what they made together is kept
        self.join(OWNER, 60)
        self.save(OWNER, b"later edit", 61)
        first, second = kept(self.file)
        self.assertEqual(stored(first), b"v0")
        self.assertEqual(stored(second), b"owner and editor edit")
        self.assertEqual(sorted(versions._people(second.editors)), sorted([OWNER, EDITOR]))

    def test_two_people_opening_at_once(self):
        # The second CheckFileInfo finds the row the first one created a moment earlier
        doc = frappe.get_doc("File", self.file)
        real_exists = frappe.db.exists
        with self.at(0), patch.object(frappe.db, "exists", side_effect=lambda *a, **k: None if a[:1] == (versions.SESSION,) else real_exists(*a, **k)):
            versions.note_editor(doc, OWNER)
            versions.note_editor(doc, EDITOR)
        self.assertEqual(
            sorted(versions._people(frappe.db.get_value(versions.SESSION, self.file, "next_editors"))), sorted([OWNER, EDITOR])
        )

    def test_someone_who_opens_a_quiet_file_joins_the_next_session(self):
        self.save(OWNER, b"v1", 0)
        self.join(EDITOR, 45)  # the owner's session went quiet at 30
        self.save(EDITOR, b"v2", 46)
        self.save(OWNER, b"v3", 100)
        last = kept(self.file)[-1]
        self.assertEqual(stored(last), b"v2")
        self.assertEqual(versions._people(last.editors), [EDITOR])

    def test_a_long_session_is_cut_after_two_hours(self):
        for i, minute in enumerate(range(0, 160, 20)):  # never 30 quiet minutes, past 2 hours at 140
            self.save(OWNER, f"v{i + 1}".encode(), minute)
        self.assertEqual(len(kept(self.file)), 2)

    def test_retention_like_google_drive(self):
        with patch.object(versions, "KEEP_COUNT", 3):
            for i in range(6):
                self.save(OWNER, f"v{i + 1}".encode(), i * 40)
                if i == 0:
                    versions.name_version(kept(self.file)[0].name, "原本")
            left = kept(self.file)
            unnamed = [v for v in left if not v.label]
            self.assertEqual(len(unnamed), 3)
            self.assertEqual([v.label for v in left if v.label], ["原本"])
            # Unnamed versions go after 30 days; named ones stay
            versions.prune(self.file, now=self.t0 + timedelta(days=31))
            self.assertEqual([v.label for v in kept(self.file)], ["原本"])

    def test_named_versions_are_limited(self):
        with patch.object(versions, "KEEP_COUNT", 10), patch.object(versions, "NAMED_MAX", 2):
            for i in range(3):
                self.save(OWNER, f"v{i + 1}".encode(), i * 40)
            a, b, c = kept(self.file)
            versions.name_version(a.name, "A")
            versions.name_version(b.name, "B")
            self.assertRaises(frappe.ValidationError, versions.name_version, c.name, "C")
            versions.name_version(a.name, "A2")  # renaming a named one is fine

    def test_restore_keeps_what_it_replaces(self):
        self.save(OWNER, b"v1", 0)
        original = kept(self.file)[0]
        frappe.set_user(EDITOR)
        with self.at(3):
            self.assertRaises(frappe.ValidationError, versions.restore_version, original.name)
        with self.at(40):
            versions.restore_version(original.name)
        self.assertEqual(content(self.file), b"v0")
        self.assertEqual(stored(kept(self.file)[-1]), b"v1")
        self.assertEqual(frappe.db.get_value("File", self.file, "file_size"), 2)

    def test_only_editors_see_versions(self):
        self.save(OWNER, b"v1", 0)
        frappe.set_user(EDITOR)
        self.assertEqual(len(versions.list_versions(self.file)["versions"]), 1)
        frappe.set_user(READER)
        self.assertRaises(frappe.PermissionError, versions.list_versions, self.file)
        self.assertRaises(frappe.PermissionError, versions.download_version, kept(self.file)[0].name)

    def test_download_a_version_with_a_japanese_name(self):
        from werkzeug.test import EnvironBuilder

        self.save(OWNER, b"v1", 0)
        [v] = kept(self.file)
        frappe.set_user(EDITOR)
        req = SimpleNamespace(environ=EnvironBuilder().get_environ())
        with patch.object(frappe, "request", req, create=True):
            res = versions.download_version(v.name)
        res.direct_passthrough = False
        self.assertEqual(res.get_data(), b"v0")
        disposition = res.headers["Content-Disposition"]
        disposition.encode("latin-1")  # what the server writes; it failed on raw Japanese
        self.assertIn("filename*=UTF-8''", disposition)

    def test_versions_count_toward_storage_and_go_with_the_file(self):
        frappe.set_user(OWNER)
        before = storage_usage(self.team)["total_size"]
        self.save(OWNER, b"v1", 0)
        frappe.set_user(OWNER)
        self.assertEqual(storage_usage(self.team)["total_size"], before + 2)
        [v] = kept(self.file)
        path = FileManager().site_folder / v.storage_path
        self.assertTrue(path.exists())
        frappe.set_user("Administrator")
        frappe.delete_doc("File", self.file, ignore_permissions=True, force=True)
        self.assertEqual(kept(self.file), [])
        self.assertFalse(path.exists())
        self.assertFalse(frappe.db.exists(versions.SESSION, self.file))
