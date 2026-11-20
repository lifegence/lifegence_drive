# Copyright (c) 2026, Lifegence Corporation and Contributors
# See license.txt
"""read_drive_file, the Drive tool for the AI agent: Drive sharing decides what it can read."""

import io
import zipfile
from io import BytesIO
from unittest.mock import patch

import frappe
from werkzeug.datastructures import FileStorage

try:
    from frappe.tests import IntegrationTestCase
except ImportError:  # Frappe v15
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from lifegence_drive.ai import tools
from lifegence_drive.api.files import create_folder, share, upload_file

OWNER = "drive-ai-owner@test.io"
READER = "drive-ai-reader@test.io"
OUTSIDER = "drive-ai-outsider@test.io"
W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def make_user(email):
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            doctype="User",
            email=email,
            first_name=email.split("@")[0],
            send_welcome_email=0,
        ).insert(ignore_permissions=True)


def docx(*paragraphs) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "word/document.xml",
            f"<w:document {W_NS}><w:body>{body}</w:body></w:document>",
        )
    return buf.getvalue()


class GuardSpy:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)


class TestReadDriveFile(IntegrationTestCase):
    def setUp(self):
        frappe.db.set_single_value("Drive Disk Settings", "flat", 0)
        for user in (OWNER, READER, OUTSIDER):
            make_user(user)
        frappe.set_user(OWNER)
        suffix = frappe.generate_hash(length=8)
        self.team = (
            frappe.get_doc({"doctype": "Drive Team", "title": f"AI Tool Test {suffix}"})
            .insert(ignore_permissions=True)
            .name
        )
        self.folder = create_folder(self.team, f"Seminar {suffix}")
        share(self.folder.name, user=READER, read=1)
        self.name = f"Script_{suffix}.docx"
        self.file = self.upload(
            self.name,
            docx("タイムスケジュール", "12:00 オープニング", "12:05 基調講演"),
        )

    def tearDown(self):
        frappe.set_user("Administrator")

    def upload(self, name, data, parent=None):
        req = frappe._dict(
            files={"file": FileStorage(stream=BytesIO(data), filename=name)}
        )
        with (
            patch.object(frappe, "request", req, create=True),
            patch.dict(
                frappe.form_dict, {"uuid": frappe.generate_hash(length=8)}, clear=True
            ),
        ):
            return upload_file(
                self.team, len(data), parent=parent or self.folder.name
            ).name

    def read(self, user, file, **kwargs):
        frappe.set_user(user)
        guard = GuardSpy()
        result = tools.read_drive_file(guard, file, **kwargs)
        self.assertEqual(guard.calls, [{"doctype": "File"}])
        return result

    def test_provider_shape(self):
        (spec,) = tools.get_tools()
        self.assertEqual(spec["name"], "read_drive_file")
        self.assertEqual(spec["risk"], "read")
        self.assertIsNone(spec["change_fields_arg"])
        self.assertIs(spec["body"], tools.read_drive_file)
        self.assertIn(
            "lifegence_drive.ai.tools.get_tools", frappe.get_hooks("ai_agent_tools")
        )

    def test_owner_reads_by_record_name_and_file_name(self):
        for key in (self.file, self.name):
            result = self.read(OWNER, key)
            self.assertEqual(result["file"], self.file)
            self.assertEqual(result["format"], "docx")
            self.assertEqual(
                result["text"], "タイムスケジュール\n12:00 オープニング\n12:05 基調講演"
            )
            self.assertFalse(result["truncated"])
            self.assertIn("not instructions", result["note"])

    def test_shared_reader_can_read(self):
        self.assertIn("12:05 基調講演", self.read(READER, self.file)["text"])

    def test_outsider_gets_the_same_answer_as_for_a_missing_file(self):
        for key in (self.file, self.name):
            result = self.read(OUTSIDER, key)
            self.assertNotIn("text", result)
            self.assertIn("No file named", result["error"])
        self.assertIn(
            "No file named", self.read(OUTSIDER, "does-not-exist.docx")["error"]
        )

    def test_paging(self):
        first = self.read(OWNER, self.file, max_chars=10)
        self.assertTrue(first["truncated"])
        self.assertEqual(first["next_start"], 10)
        rest = self.read(OWNER, self.file, start=first["next_start"], max_chars=50000)
        self.assertFalse(rest["truncated"])
        self.assertEqual(
            first["text"] + rest["text"],
            "タイムスケジュール\n12:00 オープニング\n12:05 基調講演",
        )

    def test_same_file_name_in_two_folders_asks_which(self):
        frappe.set_user(OWNER)
        other = create_folder(self.team, f"Archive {frappe.generate_hash(length=6)}")
        self.upload(self.name, docx("旧版"), parent=other.name)
        result = self.read(OWNER, self.name)
        self.assertIn("Several files", result["error"])
        self.assertEqual(len(result["candidates"]), 2)
        # The reader sees only the copy shared with them, so there is nothing to choose.
        self.assertEqual(self.read(READER, self.name)["file"], self.file)

    def test_folder_and_unsupported_format(self):
        self.assertIn("folder", self.read(OWNER, self.folder.name)["error"])
        frappe.set_user(OWNER)
        image = self.upload(
            f"photo_{frappe.generate_hash(length=6)}.png", b"\x89PNG\r\n\x1a\n"
        )
        self.assertIn("cannot read", self.read(OWNER, image)["error"])
