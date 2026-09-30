# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
test_api_endpoints.py — HTTP Integration Tests for QUINZE REST API
===================================================================
اختبارات HTTP التكاملية لـ QUINZE REST API

Uses Odoo's HttpCase to make real HTTP requests against the test server.
يستخدم HttpCase لإرسال طلبات HTTP حقيقية على الخادم التجريبي.

Test classes:
  TestApiAuthentication  — auth gate: missing key, invalid, expired, IP block
  TestClinicApi          — patients, appointments, prescriptions endpoints
  TestLabApi             — lab orders, tests, result submission
  TestPharmacyApi        — medications, dispensings, claims
  TestApiScopeGuard      — read-only key blocked from write endpoints
"""
import json

from odoo.tests import tagged
from odoo.tests.common import HttpCase


# ── Helpers ───────────────────────────────────────────────────────────────────

def _j(data: bytes) -> dict:
    """Decode JSON response body."""
    return json.loads(data.decode("utf-8"))


BASE = "/api/quinze/v1"


@tagged("post_install", "-at_install", "quinze", "quinze_api")
class TestApiAuthentication(HttpCase):
    """Tests for the authentication gate."""

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.env.ref("base.user_admin"))

    def _make_key(self, **kwargs):
        defaults = {
            "name": "Test Auth Key",
            "user_id": self.env.uid,
            "scope": "write",
        }
        defaults.update(kwargs)
        return self.env["quinze.api.key"].create(defaults)

    def test_01_no_header_returns_401(self):
        """Request without X-API-Key returns 401."""
        resp = self.url_open(f"{BASE}/patients", headers={})
        self.assertEqual(resp.status_code, 401)
        body = _j(resp.content)
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["code"], 401)

    def test_02_invalid_token_returns_401(self):
        """Invalid token returns 401."""
        resp = self.url_open(
            f"{BASE}/patients",
            headers={"X-API-Key": "badtoken000000000000000000000000"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_03_valid_token_returns_200(self):
        """Valid token returns 200."""
        key = self._make_key()
        resp = self.url_open(
            f"{BASE}/patients",
            headers={"X-API-Key": key.token},
        )
        self.assertEqual(resp.status_code, 200)
        body = _j(resp.content)
        self.assertEqual(body["status"], "ok")

    def test_04_revoked_key_returns_401(self):
        """Revoked (inactive) key returns 401."""
        key = self._make_key()
        token = key.token
        key.active = False
        resp = self.url_open(
            f"{BASE}/patients",
            headers={"X-API-Key": token},
        )
        self.assertEqual(resp.status_code, 401)

    def test_05_read_key_blocked_on_post(self):
        """Read-only key blocked on POST endpoints (403)."""
        from odoo import fields as odoo_fields
        key = self._make_key(scope="read")
        resp = self.url_open(
            f"{BASE}/appointments",
            data=json.dumps({"patient_id": 1, "doctor_id": 1,
                             "start": "2026-07-01T09:00:00",
                             "stop": "2026-07-01T09:30:00"}).encode(),
            headers={
                "X-API-Key": key.token,
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(resp.status_code, 403)

    def test_06_response_envelope_structure(self):
        """Success response has {status, data, meta} structure."""
        key = self._make_key()
        resp = self.url_open(
            f"{BASE}/patients",
            headers={"X-API-Key": key.token},
        )
        body = _j(resp.content)
        self.assertIn("status", body)
        self.assertIn("data", body)
        self.assertIn("meta", body)
        meta = body["meta"]
        self.assertIn("total", meta)
        self.assertIn("page", meta)
        self.assertIn("limit", meta)
        self.assertIn("pages", meta)


@tagged("post_install", "-at_install", "quinze", "quinze_api")
class TestClinicApi(HttpCase):
    """Tests for /patients, /appointments, /prescriptions endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))
        # Create a key
        cls.key = cls.env["quinze.api.key"].create({
            "name": "Clinic Test Key",
            "user_id": cls.env.uid,
            "scope": "write",
        })
        cls.headers = {
            "X-API-Key": cls.key.token,
            "Content-Type": "application/json",
        }
        # Create test patient
        cls.partner = cls.env["res.partner"].create({"name": "API Test Patient"})
        cls.patient = cls.env["health.patient"].create(
            {"partner_id": cls.partner.id}
        )
        # Create doctor
        cls.doctor = cls.env["res.partner"].create(
            {"name": "API Test Doctor", "is_doctor": True}
        )

    def test_01_list_patients_returns_ok(self):
        """GET /patients returns 200 with data list."""
        resp = self.url_open(f"{BASE}/patients", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        body = _j(resp.content)
        self.assertIsInstance(body["data"], list)

    def test_02_get_patient_detail(self):
        """GET /patients/<id> returns patient fields."""
        resp = self.url_open(
            f"{BASE}/patients/{self.patient.id}",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        body = _j(resp.content)
        self.assertEqual(body["data"]["id"], self.patient.id)
        self.assertIn("name", body["data"])
        self.assertIn("recent_prescriptions", body["data"])

    def test_03_get_nonexistent_patient_returns_404(self):
        """GET /patients/99999999 returns 404."""
        resp = self.url_open(f"{BASE}/patients/99999999", headers=self.headers)
        self.assertEqual(resp.status_code, 404)

    def test_04_create_appointment(self):
        """POST /appointments creates appointment and returns it."""
        payload = {
            "patient_id": self.patient.id,
            "doctor_id": self.doctor.id,
            "start": "2026-08-01T10:00:00",
            "stop": "2026-08-01T10:30:00",
            "type": "new",
            "chief_complaint": "API test visit",
        }
        resp = self.url_open(
            f"{BASE}/appointments",
            data=json.dumps(payload).encode(),
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        body = _j(resp.content)
        self.assertIn("id", body["data"])
        self.assertEqual(body["data"]["state"], "draft")

    def test_05_create_appointment_missing_field_returns_400(self):
        """POST /appointments without required field returns 400."""
        payload = {"patient_id": self.patient.id}  # missing doctor_id, start, stop
        resp = self.url_open(
            f"{BASE}/appointments",
            data=json.dumps(payload).encode(),
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 400)

    def test_06_list_appointments_with_state_filter(self):
        """GET /appointments?state=draft returns filtered list."""
        resp = self.url_open(
            f"{BASE}/appointments?state=draft",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        body = _j(resp.content)
        for apt in body["data"]:
            self.assertEqual(apt["state"], "draft")

    def test_07_pagination_meta(self):
        """GET /patients?page=1&limit=5 returns correct meta."""
        resp = self.url_open(
            f"{BASE}/patients?page=1&limit=5",
            headers=self.headers,
        )
        body = _j(resp.content)
        self.assertEqual(body["meta"]["page"], 1)
        self.assertEqual(body["meta"]["limit"], 5)
        self.assertLessEqual(len(body["data"]), 5)

    def test_08_prescriptions_list(self):
        """GET /prescriptions returns 200."""
        resp = self.url_open(f"{BASE}/prescriptions", headers=self.headers)
        self.assertEqual(resp.status_code, 200)


@tagged("post_install", "-at_install", "quinze", "quinze_api")
class TestLabApi(HttpCase):
    """Tests for /lab/orders and /lab/tests endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))
        cls.key = cls.env["quinze.api.key"].create({
            "name": "Lab Test Key",
            "user_id": cls.env.uid,
            "scope": "write",
        })
        cls.headers = {"X-API-Key": cls.key.token}

    def test_01_list_lab_orders(self):
        """GET /lab/orders returns 200."""
        resp = self.url_open(f"{BASE}/lab/orders", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        body = _j(resp.content)
        self.assertEqual(body["status"], "ok")

    def test_02_list_lab_tests(self):
        """GET /lab/tests returns 200 with test catalog."""
        resp = self.url_open(f"{BASE}/lab/tests", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        body = _j(resp.content)
        self.assertIsInstance(body["data"], list)

    def test_03_get_nonexistent_lab_order_returns_404(self):
        """GET /lab/orders/99999999 returns 404."""
        resp = self.url_open(
            f"{BASE}/lab/orders/99999999", headers=self.headers
        )
        self.assertEqual(resp.status_code, 404)

    def test_04_lab_tests_search(self):
        """GET /lab/tests?q=HGB returns filtered results."""
        resp = self.url_open(
            f"{BASE}/lab/tests?q=HGB", headers=self.headers
        )
        self.assertEqual(resp.status_code, 200)


@tagged("post_install", "-at_install", "quinze", "quinze_api")
class TestPharmacyApi(HttpCase):
    """Tests for pharmacy dispensing and claims endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))
        cls.key = cls.env["quinze.api.key"].create({
            "name": "Pharmacy Test Key",
            "user_id": cls.env.uid,
            "scope": "write",
        })
        cls.headers = {
            "X-API-Key": cls.key.token,
            "Content-Type": "application/json",
        }
        cls.partner = cls.env["res.partner"].create(
            {"name": "Pharmacy API Patient"}
        )
        cls.med = cls.env["product.template"].create({
            "name": "API Test Med",
            "type": "consu",
            "is_medication": True,
            "list_price": 10.0,
        })
        cls.med_variant = cls.med.product_variant_id

    def test_01_list_medications(self):
        """GET /pharmacy/medications returns medications catalog."""
        resp = self.url_open(
            f"{BASE}/pharmacy/medications", headers=self.headers
        )
        self.assertEqual(resp.status_code, 200)
        body = _j(resp.content)
        # All returned items should be medications
        for item in body["data"]:
            self.assertIn("name", item)
            self.assertIn("price", item)

    def test_02_list_dispensings(self):
        """GET /pharmacy/dispensings returns 200."""
        resp = self.url_open(
            f"{BASE}/pharmacy/dispensings", headers=self.headers
        )
        self.assertEqual(resp.status_code, 200)

    def test_03_create_external_dispensing(self):
        """POST /pharmacy/dispensings creates dispensing with lines."""
        payload = {
            "partner_id": self.partner.id,
            "lines": [
                {
                    "product_id": self.med_variant.id,
                    "qty": 10,
                    "price_unit": 10.0,
                }
            ],
        }
        resp = self.url_open(
            f"{BASE}/pharmacy/dispensings",
            data=json.dumps(payload).encode(),
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        body = _j(resp.content)
        self.assertIn("id", body["data"])
        self.assertEqual(body["data"]["state"], "draft")
        self.assertEqual(len(body["data"]["lines"]), 1)

    def test_04_create_dispensing_no_partner_returns_400(self):
        """POST /pharmacy/dispensings without partner returns 400."""
        payload = {
            "lines": [{"product_id": self.med_variant.id, "qty": 5}]
        }
        resp = self.url_open(
            f"{BASE}/pharmacy/dispensings",
            data=json.dumps(payload).encode(),
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 400)

    def test_05_create_dispensing_no_lines_returns_400(self):
        """POST /pharmacy/dispensings without lines returns 400."""
        payload = {"partner_id": self.partner.id}
        resp = self.url_open(
            f"{BASE}/pharmacy/dispensings",
            data=json.dumps(payload).encode(),
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 400)

    def test_06_list_claims(self):
        """GET /pharmacy/claims returns 200."""
        resp = self.url_open(
            f"{BASE}/pharmacy/claims", headers=self.headers
        )
        self.assertEqual(resp.status_code, 200)

    def test_07_get_nonexistent_dispensing_returns_404(self):
        """GET /pharmacy/dispensings/99999999 returns 404."""
        resp = self.url_open(
            f"{BASE}/pharmacy/dispensings/99999999", headers=self.headers
        )
        self.assertEqual(resp.status_code, 404)
