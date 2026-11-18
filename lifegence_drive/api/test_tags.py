# Copyright (c) 2026, Lifegence Corporation and Contributors
# See license.txt

import frappe

try:
    from frappe.tests import IntegrationTestCase
except ImportError:  # Frappe v15
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from lifegence_drive.api.files import create_folder, share
from lifegence_drive.api.list import files, tagged
from lifegence_drive.api.tags import add_tag, get_entity_tags, get_tags, remove_tag

OWNER = "drive-tags-owner@test.io"
VIEWER = "drive-tags-viewer@test.io"
OUTSIDER = "drive-tags-outsider@test.io"


def make_user(email):
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            doctype="User", email=email, first_name=email.split("@")[0], send_welcome_email=0
        ).insert(ignore_permissions=True)


class TestTags(IntegrationTestCase):
    def setUp(self):
        for user in (OWNER, VIEWER, OUTSIDER):
            make_user(user)
        frappe.set_user(OWNER)
        self.label = "Invoice " + frappe.generate_hash(length=6)
        self.team = frappe.get_doc(
            {"doctype": "Drive Team", "title": "Tags Test " + frappe.generate_hash(length=8)}
        ).insert(ignore_permissions=True)
        self.a = create_folder(self.team.name, "A")
        self.b = create_folder(self.team.name, "B")
        share(self.a.name, user=VIEWER, read=1)

    def tearDown(self):
        frappe.set_user("Administrator")

    def links(self, name):
        return frappe.get_all(
            "Tag Link", filters={"document_type": "File", "document_name": name}, pluck="tag"
        )

    def test_add_and_remove_keep_tag_links_in_step(self):
        add_tag([self.a.name, self.b.name], f"  {self.label}  ")
        self.assertEqual(get_entity_tags(self.a.name), [self.label])
        self.assertEqual(self.links(self.b.name), [self.label])
        self.assertTrue(frappe.db.exists("Tag", self.label))

        remove_tag(self.a.name, self.label.upper())
        self.assertEqual(get_entity_tags(self.a.name), [])
        self.assertEqual(self.links(self.a.name), [])
        self.assertEqual(get_entity_tags(self.b.name), [self.label])

    def test_same_tag_in_another_case_is_not_added_twice(self):
        add_tag(self.a.name, self.label)
        add_tag(self.a.name, self.label.lower())
        self.assertEqual(get_entity_tags(self.a.name), [self.label])

    def test_invalid_tags_are_rejected(self):
        for bad in ("", "   ", "a,b", "x" * 141):
            with self.assertRaises(ValueError):
                add_tag(self.a.name, bad)

    def test_read_only_access_cannot_tag(self):
        frappe.set_user(VIEWER)
        self.assertEqual(get_entity_tags(self.a.name), [])
        with self.assertRaises(frappe.PermissionError):
            add_tag(self.a.name, self.label)

    def test_no_access_cannot_read_tags(self):
        frappe.set_user(OUTSIDER)
        with self.assertRaises(frappe.PermissionError):
            get_entity_tags(self.b.name)

    def test_tag_list_and_tagged_files(self):
        add_tag([self.a.name, self.b.name], self.label)
        counts = {t["tag"]: t["count"] for t in get_tags(self.team.name)}
        self.assertEqual(counts.get(self.label), 2)

        folders = tagged(self.team.name)
        self.assertIn(self.label, [f["tag"] for f in folders])

        names = {f["name"] for f in tagged(self.team.name, tag=self.label)}
        self.assertEqual(names, {self.a.name, self.b.name})

    def test_tagged_files_hide_teams_the_user_is_not_in(self):
        add_tag(self.a.name, self.label)
        frappe.set_user(OUTSIDER)
        self.assertEqual(get_tags(), [])
        self.assertEqual(tagged("all", tag=self.label), [])

    def test_folder_listing_carries_tags(self):
        add_tag(self.a.name, self.label)
        rows = {r["name"]: r for r in files(self.team.name)}
        self.assertEqual(rows[self.a.name]["tags"], [self.label])
        self.assertEqual(rows[self.b.name]["tags"], [])

    def test_empty_team_spans_all_teams(self):
        other = frappe.get_doc(
            {"doctype": "Drive Team", "title": "Tags Test " + frappe.generate_hash(length=8)}
        ).insert(ignore_permissions=True)
        c = create_folder(other.name, "C")
        add_tag([self.a.name, c.name], self.label)
        names = {f["name"] for f in tagged(tag=self.label)}
        self.assertEqual(names, {self.a.name, c.name})
