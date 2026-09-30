# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
Tests for quinze_health_lab
============================
اختبارات موديول مختبر نظام QUINZE

Covers:
    - lab.test.category : create, uniqueness
    - lab.test           : create, reference range gender selection
    - lab.order          : state machine, auto-complete, conflict guards
    - lab.order.line     : flag computation (normal/high/low/critical)
    - lab.sample         : state machine, rejection guard
    - health.lab.request : bridge hook creates lab.order
    - End-to-end         : request → order → sample → results → done
"""

from datetime import date, datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "quinze", "quinze_lab")
class TestLabTestCategory(TransactionCase):
    """lab.test.category: create, code uniqueness."""

    def test_01_create_category(self):
        cat = self.env["lab.test.category"].create(
            {"name": "Hematology", "name_ar": "أمراض الدم", "code": "HEM-T"}
        )
        self.assertTrue(cat.id)
        self.assertEqual(cat.code, "HEM-T")

    def test_02_code_unique_per_company(self):
        self.env["lab.test.category"].create(
            {"name": "Unique Cat", "code": "UCAT1"}
        )
        with self.assertRaises(Exception):
            self.env["lab.test.category"].create(
                {"name": "Duplicate Cat", "code": "UCAT1"}
            )


@tagged("post_install", "-at_install", "quinze", "quinze_lab")
class TestLabTest(TransactionCase):
    """lab.test: reference range gender selection."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cat = cls.env["lab.test.category"].create(
            {"name": "Chemistry Test", "code": "CHEM-T"}
        )

    def _make_test(self, code="TST01", **kwargs):
        vals = {
            "name": "Test " + code,
            "code": code,
            "category_id": self.cat.id,
            "result_type": "numeric",
            "sample_type": "blood_venous",
        }
        vals.update(kwargs)
        return self.env["lab.test"].create(vals)

    def test_01_universal_range(self):
        t = self._make_test(ref_low=4.0, ref_high=11.0)
        low, high = t.get_reference_range("male")
        self.assertEqual(low, 4.0)
        self.assertEqual(high, 11.0)

    def test_02_gender_specific_male(self):
        t = self._make_test(
            ref_low=3.8, ref_high=5.9,
            ref_low_male=4.5, ref_high_male=5.9,
            ref_low_female=3.8, ref_high_female=5.2,
        )
        low, high = t.get_reference_range("male")
        self.assertEqual(low, 4.5)
        self.assertEqual(high, 5.9)

    def test_03_gender_specific_female(self):
        t = self._make_test(
            ref_low=3.8, ref_high=5.9,
            ref_low_male=4.5, ref_high_male=5.9,
            ref_low_female=3.8, ref_high_female=5.2,
        )
        low, high = t.get_reference_range("female")
        self.assertEqual(low, 3.8)
        self.assertEqual(high, 5.2)

    def test_04_fallback_to_universal(self):
        """If no gender-specific range, falls back to universal."""
        t = self._make_test(ref_low=70.0, ref_high=100.0)
        low, high = t.get_reference_range("female")
        self.assertEqual(low, 70.0)
        self.assertEqual(high, 100.0)


@tagged("post_install", "-at_install", "quinze", "quinze_lab")
class TestLabOrderLine(TransactionCase):
    """lab.order.line: flag computation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cat = cls.env["lab.test.category"].create(
            {"name": "Flag Cat", "code": "FLAGC"}
        )
        cls.test = cls.env["lab.test"].create(
            {
                "name": "Flag Test",
                "code": "FLAG01",
                "category_id": cat.id,
                "result_type": "numeric",
                "sample_type": "blood_venous",
                "ref_low": 70.0,
                "ref_high": 100.0,
                "critical_low": 40.0,
                "critical_high": 500.0,
                "result_uom": "mg/dL",
            }
        )
        patient_partner = cls.env["res.partner"].create(
            {
                "name": "Flag Patient",
                "is_patient": True,
                "national_id": "8881234567",
            }
        )
        cls.patient = cls.env["health.patient"].create(
            {"partner_id": patient_partner.id}
        )
        cls.order = cls.env["lab.order"].create(
            {
                "patient_id": cls.patient.id,
                "order_date": date.today(),
            }
        )

    def _make_line(self, result_value, ref_low=70.0, ref_high=100.0):
        return self.env["lab.order.line"].create(
            {
                "order_id": self.order.id,
                "test_id": self.test.id,
                "ref_low": ref_low,
                "ref_high": ref_high,
                "result_value": result_value,
            }
        )

    def test_01_flag_normal(self):
        line = self._make_line(85.0)
        self.assertEqual(line.flag, "normal")

    def test_02_flag_high(self):
        line = self._make_line(120.0)
        self.assertEqual(line.flag, "high")

    def test_03_flag_low(self):
        line = self._make_line(60.0)
        self.assertEqual(line.flag, "low")

    def test_04_flag_critical_high(self):
        line = self._make_line(600.0)
        self.assertEqual(line.flag, "critical_high")

    def test_05_flag_critical_low(self):
        line = self._make_line(30.0)
        self.assertEqual(line.flag, "critical_low")

    def test_06_flag_on_boundary_high(self):
        """Exactly at ref_high → normal."""
        line = self._make_line(100.0)
        self.assertEqual(line.flag, "normal")

    def test_07_flag_on_boundary_low(self):
        """Exactly at ref_low → normal."""
        line = self._make_line(70.0)
        self.assertEqual(line.flag, "normal")

    def test_08_enter_result_sets_state(self):
        line = self._make_line(88.0)
        line.action_enter_result()
        self.assertEqual(line.state, "resulted")


@tagged("post_install", "-at_install", "quinze", "quinze_lab")
class TestLabSample(TransactionCase):
    """lab.sample: state machine and rejection guard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        patient_partner = cls.env["res.partner"].create(
            {"name": "Sample Patient", "is_patient": True, "national_id": "7771234567"}
        )
        cls.patient = cls.env["health.patient"].create(
            {"partner_id": patient_partner.id}
        )
        cls.order = cls.env["lab.order"].create(
            {"patient_id": cls.patient.id, "order_date": date.today()}
        )

    def _make_sample(self):
        return self.env["lab.sample"].create(
            {
                "lab_order_id": self.order.id,
                "sample_type": "blood_venous",
            }
        )

    def test_01_sample_number_assigned(self):
        s = self._make_sample()
        self.assertTrue(s.name)
        self.assertNotEqual(s.name, "New")

    def test_02_collect(self):
        s = self._make_sample()
        s.action_collect()
        self.assertEqual(s.state, "collected")
        self.assertTrue(s.collection_datetime)

    def test_03_receive(self):
        s = self._make_sample()
        s.action_collect()
        s.action_receive()
        self.assertEqual(s.state, "received")
        self.assertTrue(s.received_datetime)

    def test_04_reject_requires_reason(self):
        s = self._make_sample()
        s.action_collect()
        with self.assertRaises(UserError):
            s.action_reject()

    def test_05_reject_with_reason(self):
        s = self._make_sample()
        s.action_collect()
        s.rejection_reason = "Haemolysed / العينة متحللة"
        s.action_reject()
        self.assertEqual(s.state, "rejected")


@tagged("post_install", "-at_install", "quinze", "quinze_lab")
class TestLabOrder(TransactionCase):
    """lab.order: state machine, no tests guard, auto-complete."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cat = cls.env["lab.test.category"].create(
            {"name": "Order Cat", "code": "ORDC"}
        )
        cls.test = cls.env["lab.test"].create(
            {
                "name": "Order Test",
                "code": "ORDT01",
                "category_id": cat.id,
                "result_type": "numeric",
                "sample_type": "blood_venous",
                "ref_low": 4.0,
                "ref_high": 11.0,
                "result_uom": "10³/µL",
            }
        )
        patient_partner = cls.env["res.partner"].create(
            {"name": "Order Patient", "is_patient": True, "national_id": "6661234567"}
        )
        cls.patient = cls.env["health.patient"].create(
            {"partner_id": patient_partner.id}
        )

    def _make_order(self):
        return self.env["lab.order"].create(
            {"patient_id": self.patient.id, "order_date": date.today()}
        )

    def test_01_order_number_assigned(self):
        o = self._make_order()
        self.assertTrue(o.order_number.startswith("LAB/"))

    def test_02_collect_requires_lines(self):
        o = self._make_order()
        with self.assertRaises(UserError):
            o.action_collect_sample()

    def test_03_collect_with_lines(self):
        o = self._make_order()
        self.env["lab.order.line"].create(
            {
                "order_id": o.id,
                "test_id": self.test.id,
                "ref_low": 4.0,
                "ref_high": 11.0,
            }
        )
        o.action_collect_sample()
        self.assertEqual(o.state, "sample_collected")
        self.assertTrue(o.sample_ids)

    def test_04_auto_complete_on_all_results(self):
        """Order moves to done automatically when all lines are resulted."""
        o = self._make_order()
        line = self.env["lab.order.line"].create(
            {
                "order_id": o.id,
                "test_id": self.test.id,
                "ref_low": 4.0,
                "ref_high": 11.0,
            }
        )
        # Force to in_progress
        o.state = "in_progress"
        line.result_value = 7.5
        line.action_enter_result()
        self.assertEqual(o.state, "done")
        self.assertTrue(o.completed_date)

    def test_05_cancel(self):
        o = self._make_order()
        o.action_cancel()
        self.assertEqual(o.state, "cancelled")

    def test_06_reset_draft(self):
        o = self._make_order()
        o.action_cancel()
        o.action_reset_draft()
        self.assertEqual(o.state, "draft")


@tagged("post_install", "-at_install", "quinze", "quinze_lab")
class TestBridgeHook(TransactionCase):
    """health.lab.request: bridge override creates lab.order."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        doctor = cls.env["res.partner"].create(
            {"name": "Dr. Bridge", "is_doctor": True}
        )
        patient_partner = cls.env["res.partner"].create(
            {"name": "Bridge Patient", "is_patient": True, "national_id": "5551234567"}
        )
        cls.patient = cls.env["health.patient"].create(
            {"partner_id": patient_partner.id}
        )
        cls.doctor = doctor
        cls.encounter = cls.env["health.encounter"].create(
            {
                "patient_id": cls.patient.id,
                "doctor_id": cls.doctor.id,
                "chief_complaint": "Bridge test",
            }
        )

    def test_01_confirm_creates_lab_order(self):
        req = self.env["health.lab.request"].create(
            {
                "encounter_id": self.encounter.id,
                "request_date": date.today(),
                "tests_description": "CBC",
                "priority": "0",
            }
        )
        req.action_confirm()
        self.assertTrue(req.lab_order_id)
        self.assertEqual(req.lab_order_id.patient_id, self.patient)

    def test_02_idempotent_no_duplicate(self):
        """Confirming twice should not create a second lab.order."""
        req = self.env["health.lab.request"].create(
            {
                "encounter_id": self.encounter.id,
                "request_date": date.today(),
                "tests_description": "Lipids",
                "priority": "1",
            }
        )
        req.action_confirm()
        order_id_1 = req.lab_order_id.id
        # Call hook again directly
        req._action_create_lab_order()
        self.assertEqual(req.lab_order_id.id, order_id_1)


@tagged("post_install", "-at_install", "quinze", "quinze_lab")
class TestLabEndToEnd(TransactionCase):
    """
    End-to-end: lab request confirmed → order created → sample collected →
    received → results entered → auto-complete → done.

    سيناريو متكامل: تأكيد طلب → إنشاء أمر → جمع عينة → استلام →
    إدخال نتائج → اكتمال تلقائي → منتهٍ.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cat = cls.env["lab.test.category"].create(
            {"name": "E2E Lab Cat", "code": "E2EC"}
        )
        cls.test_wbc = cls.env["lab.test"].create(
            {
                "name": "E2E WBC",
                "code": "E2E-WBC",
                "category_id": cat.id,
                "result_type": "numeric",
                "sample_type": "blood_venous",
                "ref_low": 4.0,
                "ref_high": 11.0,
                "result_uom": "10³/µL",
            }
        )
        cls.test_hgb = cls.env["lab.test"].create(
            {
                "name": "E2E HGB",
                "code": "E2E-HGB",
                "category_id": cat.id,
                "result_type": "numeric",
                "sample_type": "blood_venous",
                "ref_low_male": 13.5,
                "ref_high_male": 17.5,
                "ref_low_female": 12.0,
                "ref_high_female": 15.5,
                "ref_low": 12.0,
                "ref_high": 17.5,
                "critical_low": 7.0,
                "result_uom": "g/dL",
            }
        )
        doctor = cls.env["res.partner"].create(
            {"name": "Dr. E2E Lab", "is_doctor": True}
        )
        patient_partner = cls.env["res.partner"].create(
            {
                "name": "E2E Lab Patient",
                "is_patient": True,
                "national_id": "4441234567",
                "gender": "male",
            }
        )
        cls.patient = cls.env["health.patient"].create(
            {"partner_id": patient_partner.id}
        )
        cls.doctor = doctor
        cls.encounter = cls.env["health.encounter"].create(
            {
                "patient_id": cls.patient.id,
                "doctor_id": cls.doctor.id,
                "chief_complaint": "E2E lab test",
            }
        )

    def test_full_lab_workflow(self):
        # 1. Create lab request and confirm → bridge creates lab order
        req = self.env["health.lab.request"].create(
            {
                "encounter_id": self.encounter.id,
                "request_date": date.today(),
                "tests_description": "CBC",
                "priority": "1",
                "clinical_indication": "Anaemia workup",
            }
        )
        req.action_confirm()
        self.assertEqual(req.state, "confirmed")
        order = req.lab_order_id
        self.assertTrue(order)

        # 2. Add test lines to the order
        line_wbc = self.env["lab.order.line"].create(
            {"order_id": order.id, "test_id": self.test_wbc.id}
        )
        line_hgb = self.env["lab.order.line"].create(
            {"order_id": order.id, "test_id": self.test_hgb.id}
        )

        # Verify gender-specific ref range on HGB (male patient)
        self.assertAlmostEqual(line_hgb.ref_low, 13.5, places=1)
        self.assertAlmostEqual(line_hgb.ref_high, 17.5, places=1)

        # 3. Collect sample
        order.action_collect_sample()
        self.assertEqual(order.state, "sample_collected")
        self.assertTrue(order.sample_ids)

        # 4. Receive samples → order moves to in_progress
        order.action_receive_samples()
        self.assertEqual(order.state, "in_progress")

        # 5. Enter results
        line_wbc.result_value = 8.5   # Normal
        line_wbc.action_enter_result()
        self.assertEqual(line_wbc.flag, "normal")

        # HGB = 9.5 → below ref_low_male (13.5) → low
        line_hgb.result_value = 9.5
        line_hgb.action_enter_result()
        self.assertEqual(line_hgb.flag, "low")

        # 6. Auto-complete: both lines resulted → order done
        self.assertEqual(order.state, "done")
        self.assertTrue(order.completed_date)

        # 7. Counters
        order.invalidate_recordset()
        self.assertEqual(order.result_count, 2)
        self.assertEqual(order.abnormal_count, 1)  # HGB low
        self.assertEqual(order.critical_count, 0)
