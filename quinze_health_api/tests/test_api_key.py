# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
test_api_key.py — Tests for quinze.api.key model
==================================================
اختبارات موديول مفاتيح الـ API
"""
import time

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "quinze", "quinze_api")
class TestApiKey(TransactionCase):
    """Tests for quinze.api.key creation, authentication and lifecycle."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))
        cls.ApiKey = cls.env["quinze.api.key"]

    def _make_key(self, **kwargs):
        defaults = {
            "name": "Test Key",
            "user_id": self.env.uid,
            "scope": "read",
        }
        defaults.update(kwargs)
        return self.ApiKey.create(defaults)

    def test_01_token_auto_generated(self):
        """Token is auto-generated on create and is 64 chars."""
        key = self._make_key()
        self.assertIsNotNone(key.token)
        self.assertEqual(len(key.token), 64)

    def test_02_token_is_unique(self):
        """Two keys have different tokens."""
        k1 = self._make_key(name="K1")
        k2 = self._make_key(name="K2")
        self.assertNotEqual(k1.token, k2.token)

    def test_03_token_preview_first_8_chars(self):
        """token_preview shows first 8 characters + ellipsis."""
        key = self._make_key()
        self.assertTrue(key.token_preview.startswith(key.token[:8]))
        self.assertIn("…", key.token_preview)

    def test_04_authenticate_valid_token(self):
        """authenticate() returns the key for a valid token."""
        key = self._make_key()
        result = self.ApiKey.authenticate(key.token)
        self.assertEqual(result.id, key.id)

    def test_05_authenticate_invalid_token(self):
        """authenticate() returns None for an unknown token."""
        result = self.ApiKey.authenticate("invalid_token_xxxxxxxx")
        self.assertFalse(result)

    def test_06_authenticate_empty_token(self):
        """authenticate() returns None for empty string."""
        result = self.ApiKey.authenticate("")
        self.assertFalse(result)

    def test_07_authenticate_inactive_key(self):
        """authenticate() returns None for a revoked (inactive) key."""
        key = self._make_key()
        token = key.token
        key.active = False
        result = self.ApiKey.authenticate(token)
        self.assertFalse(result)

    def test_08_authenticate_expired_key(self):
        """authenticate() returns None for an expired key."""
        key = self._make_key(
            expiry_date=fields.Date.from_string("2020-01-01")
        )
        result = self.ApiKey.authenticate(key.token)
        self.assertFalse(result)

    def test_09_authenticate_ip_whitelist_match(self):
        """authenticate() succeeds when IP is in whitelist."""
        key = self._make_key(ip_whitelist="192.168.1.100\n10.0.0.1")
        result = self.ApiKey.authenticate(key.token, ip="192.168.1.100")
        self.assertTrue(result)

    def test_10_authenticate_ip_whitelist_block(self):
        """authenticate() returns None when IP is NOT in whitelist."""
        key = self._make_key(ip_whitelist="192.168.1.100")
        result = self.ApiKey.authenticate(key.token, ip="1.2.3.4")
        self.assertFalse(result)

    def test_11_authenticate_updates_request_count(self):
        """authenticate() increments request_count each call."""
        key = self._make_key()
        initial = key.request_count
        self.ApiKey.authenticate(key.token)
        self.ApiKey.authenticate(key.token)
        self.assertEqual(key.request_count, initial + 2)

    def test_12_authenticate_updates_last_used(self):
        """authenticate() sets last_used timestamp."""
        key = self._make_key()
        self.assertFalse(key.last_used)
        self.ApiKey.authenticate(key.token)
        self.assertTrue(key.last_used)

    def test_13_revoke_deactivates_key(self):
        """action_revoke() sets active = False."""
        key = self._make_key()
        key.action_revoke()
        self.assertFalse(key.active)

    def test_14_rotate_changes_token(self):
        """action_rotate() generates a new token."""
        key = self._make_key()
        old_token = key.token
        key.action_rotate()
        self.assertNotEqual(key.token, old_token)
        self.assertEqual(len(key.token), 64)

    def test_15_read_scope_key_exists(self):
        """Read-only scope key is created correctly."""
        key = self._make_key(scope="read")
        self.assertEqual(key.scope, "read")

    def test_16_write_scope_key_exists(self):
        """Read-write scope key is created correctly."""
        key = self._make_key(scope="write")
        self.assertEqual(key.scope, "write")

    def test_17_no_expiry_key_is_always_valid(self):
        """A key with no expiry_date never expires."""
        key = self._make_key(expiry_date=False)
        result = self.ApiKey.authenticate(key.token)
        self.assertTrue(result)
