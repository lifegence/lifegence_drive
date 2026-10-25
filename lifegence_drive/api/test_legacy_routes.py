# Copyright (c) 2026, Lifegence Corporation and Contributors
# See license.txt

import ast
from pathlib import Path

import frappe

try:
    from frappe.tests import IntegrationTestCase
except ImportError:  # Frappe v15
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from lifegence_drive.legacy_routes import LEGACY_METHODS
from lifegence_drive.utils.files import storage_key

API = Path(__file__).parent


def whitelisted_functions():
    for f in sorted(API.glob("*.py")):
        if f.name.startswith("test_") or f.name == "__init__.py":
            continue
        for node in ast.parse(f.read_text()).body:
            if isinstance(node, ast.FunctionDef) and any(
                getattr(getattr(d, "func", d), "attr", "") == "whitelist" for d in node.decorator_list
            ):
                yield f"{f.stem}.{node.name}"


class TestLegacyRoutes(IntegrationTestCase):
    def test_every_whitelisted_function_has_a_legacy_route(self):
        missing = sorted(set(whitelisted_functions()) - set(LEGACY_METHODS))
        self.assertEqual(missing, [], "add these to legacy_routes.py")

    def test_old_paths_resolve_to_new_functions(self):
        for method in LEGACY_METHODS:
            new = frappe.override_whitelisted_method(f"drive.api.{method}")
            self.assertEqual(new, f"lifegence_drive.api.{method}")
            self.assertTrue(callable(frappe.get_attr(new)), new)

    def test_old_s3_urls_still_resolve(self):
        old = "/api/method/drive.api.s3.fetch?path=team/a%20b.pdf"
        new = "/api/method/lifegence_drive.api.s3.fetch?path=team/a%20b.pdf"
        self.assertEqual(storage_key(old), "team/a b.pdf")
        self.assertEqual(storage_key(new), "team/a b.pdf")
