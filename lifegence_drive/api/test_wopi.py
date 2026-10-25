# Copyright (c) 2026, Lifegence Corporation and Contributors
# See license.txt

import time
from unittest.mock import patch

import frappe

try:
    from frappe.tests import IntegrationTestCase
except ImportError:  # Frappe v15
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from lifegence_drive.api import wopi


class TestWopiToken(IntegrationTestCase):
    def test_round_trip(self):
        token, expires = wopi.make_token("file-1", "a@example.com")
        self.assertEqual(wopi.read_token(token, "file-1"), "a@example.com")
        self.assertGreater(expires, time.time())

    def test_token_is_bound_to_the_file(self):
        token, _ = wopi.make_token("file-1", "a@example.com")
        self.assertIsNone(wopi.read_token(token, "file-2"))

    def test_expired_token_is_refused(self):
        token, _ = wopi.make_token("file-1", "a@example.com", ttl=-1)
        self.assertIsNone(wopi.read_token(token, "file-1"))

    def test_tampered_token_is_refused(self):
        token, _ = wopi.make_token("file-1", "a@example.com")
        other, _ = wopi.make_token("file-1", "admin@example.com")
        forged = token.split(".")[0] + "." + other.split(".")[1]
        self.assertIsNone(wopi.read_token(forged, "file-1"))
        self.assertIsNone(wopi.read_token("garbage", "file-1"))
        self.assertIsNone(wopi.read_token("", "file-1"))


class TestWopiRenderer(IntegrationTestCase):
    def test_off_without_collabora_url(self):
        with patch.dict(frappe.local.conf, {"drive_collabora_url": None}):
            self.assertFalse(wopi.WOPIPage("wopi/files/x").can_render())

    def test_on_with_collabora_url(self):
        with patch.dict(frappe.local.conf, {"drive_collabora_url": "http://collabora:9980"}):
            self.assertTrue(wopi.WOPIPage("wopi/files/x").can_render())
            self.assertFalse(wopi.WOPIPage("drive/x").can_render())
