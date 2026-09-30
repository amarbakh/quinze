# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
Tests for quinze_health_clinic
===============================
اختبارات موديول عيادة نظام QUINZE

Covers:
    - health.patient  : create, display_name, unique-partner constraint
    - health.appointment : state machine, conflict prevention, encounter creation
    - health.encounter   : vitals guard, invoicing, prescription/lab children
    - health.prescription : state machine, expiry, line qty_to_dispense
    - health.lab.request : bridge hook, confirm
"""

from datetime import date, datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "quinze", "quinze_clinic")
class TestHealthPatient(TransactionCase):
    """health.patient: creation, display_name, uniqueness."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Partner for a patient
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Patient / مريض تجريبي",
                "is_patient": True,
                "national_id": "9001112222",
                "dob": date(1990, 1, 1),
                "gender": "male",
            }
        )

    def test_01_create_patient(self):
        """Patient record is created and gets a sequence number."""
        patient = self.env["health.patient"].create(
            {"partner_id": self.partner.id}
        )
        self.assertTrue(
            patient.patient_number,
            "Patient number should be assigned from sequence",
        )
        self.assertTrue(patient.patient_number.startswith("PAT/"))

    def test_02_display_name(self):
        """display_name combines patient number and partner name."""
        patient = self.env["health.patient"].create(
            {"partner_id": self.partner.id}
        )
        self.assertIn(self.partner.name, patient.display_name)
        self.assertIn(patient.patient_number, patient.display_name)

    def test_03_partner_unique_per_company(self):
        """The same partner cannot have two health.patient records in one company."""
        self.env["health.patient"].create({"partner_id": self.partner.id})
        with self.assertRaises(
            (UserError, ValidationError),
            msg="Should prevent duplicate patient for same partner/company",
        ):
            self.env["health.patient"].create(
                {"partner_id": self.partner.id}
            )

    def test_04_related_fields_from_partner(self):
        """Related fields national_id, dob, gender are mirrored from partner."""
        patient = self.env["health.patient"].create(
            {"partner_id": self.partner.id}
        )
        self.assertEqual(patient.national_id, "9001112222")
        self.assertEqual(patient.dob, date(1990, 1, 1))
        self.assertEqual(patient.gender, "male")


@tagged("post_install", "-at_install", "quinze", "quinze_clinic")
class TestHealthRoom(TransactionCase):
    """health.room: basic creation."""

    def test_01_create_room(self):
        room = self.env["health.room"].create(
            {
                "name": "Clinic 01 / عيادة 01",
                "code": "C-01",
                "room_type": "clinic",
                "capacity": 1,
            }
        )
        self.assertEqual(room.code, "C-01")
        self.assertTrue(room.active)


@tagged("post_install", "-at_install", "quinze", "quinze_clinic")
class TestHealthAppointment(TransactionCase):
    """health.appointment: state machine and conflict prevention."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        doctor_partner = cls.env["res.partner"].create(
            {"name": "Dr. Demo / د. تجريبي", "is_doctor": True}
        )
        patient_partner = cls.env["res.partner"].create(
            {
                "name": "Patient Demo / مريض تجريبي",
                "is_patient": True,
                "national_id": "9009998888",
            }
        )
        cls.patient = cls.env["health.patient"].create(
            {"partner_id": patient_partner.id}
        )
        cls.doctor = doctor_partner
        cls.room = cls.env["health.room"].create(
            {"name": "R-Test", "code": "RT", "room_type": "clinic"}
        )
        # Base datetime for scheduling
        cls.t_start = datetime.now().replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        cls.t_stop = cls.t_start + timedelta(minutes=30)

    def _make_apt(self, start=None, stop=None, doctor=None, room=None):
        return self.env["health.appointment"].create(
            {
                "patient_id": self.patient.id,
                "doctor_id": (doctor or self.doctor).id,
                "start_datetime": start or self.t_start,
                "stop_datetime": stop or self.t_stop,
                "appointment_type": "new",
                "room_id": (room or self.room).id,
            }
        )

    def test_01_draft_to_confirmed(self):
        apt = self._make_apt()
        self.assertEqual(apt.state, "draft")
        apt.action_confirm()
        self.assertEqual(apt.state, "confirmed")

    def test_02_confirmed_to_in_progress(self):
        apt = self._make_apt()
        apt.action_confirm()
        apt.action_arrive()
        self.assertEqual(apt.state, "in_progress")

    def test_03_cancel_from_draft(self):
        apt = self._make_apt()
        apt.action_cancel()
        self.assertEqual(apt.state, "cancelled")

    def test_04_no_show(self):
        apt = self._make_apt()
        apt.action_confirm()
        apt.action_no_show()
        self.assertEqual(apt.state, "no_show")

    def test_05_doctor_conflict(self):
        """Two confirmed appointments for the same doctor at overlapping times."""
        self._make_apt()
        with self.assertRaises(
            ValidationError,
            msg="Should raise ValidationError for doctor double-booking",
        ):
            self._make_apt()

    def test_06_room_conflict(self):
        """Two appointments in the same room at overlapping times."""
        # Different doctor, same room & time → room conflict
        doctor2 = self.env["res.partner"].create(
            {"name": "Dr. Two / د. ثانٍ", "is_doctor": True}
        )
        self._make_apt()
        with self.assertRaises(
            ValidationError,
            msg="Should raise ValidationError for room double-booking",
        ):
            self._make_apt(doctor=doctor2)

    def test_07_open_encounter_creates_record(self):
        """action_open_encounter() creates a health.encounter."""
        apt = self._make_apt()
        apt.action_confirm()
        apt.action_arrive()
        action = apt.action_open_encounter()
        # The returned action should reference a health.encounter
        self.assertEqual(action.get("res_model"), "health.encounter")
        encounter = self.env["health.encounter"].browse(
            action.get("res_id") or apt.encounter_id.id
        )
        self.assertTrue(encounter.exists())
        self.assertEqual(encounter.patient_id, self.patient)

    def test_08_duration_computed(self):
        """Duration in minutes is computed from start/stop."""
        apt = self._make_apt()
        self.assertAlmostEqual(apt.duration, 30.0, places=1)


@tagged("post_install", "-at_install", "quinze", "quinze_clinic")
class TestHealthEncounter(TransactionCase):
    """health.encounter: vitals guard, action_done, invoicing."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Specialty + consultation product
        cls.specialty = cls.env["health.specialty"].create(
            {"name": "General Practice / طب عام", "code": "GP"}
        )
        cls.product = cls.env["product.template"].create(
            {
                "name": "GP Consultation / استشارة طب عام",
                "type": "service",
                "list_price": 150.0,
                "sale_ok": True,
            }
        )
        cls.specialty.consultation_product_id = cls.product.product_variant_id

        doctor_partner = cls.env["res.partner"].create(
            {
                "name": "Dr. Encounter / د. زيارة",
                "is_doctor": True,
                "specialty_id": cls.specialty.id,
            }
        )
        patient_partner = cls.env["res.partner"].create(
            {
                "name": "Encounter Patient / مريض الزيارة",
                "is_patient": True,
                "national_id": "9881112233",
            }
        )
        cls.patient = cls.env["health.patient"].create(
            {"partner_id": patient_partner.id}
        )
        cls.doctor = doctor_partner

    def _make_encounter(self, complaint="Headache / صداع"):
        return self.env["health.encounter"].create(
            {
                "patient_id": self.patient.id,
                "doctor_id": self.doctor.id,
                "chief_complaint": complaint,
            }
        )

    def _add_vitals(self, encounter):
        self.env["health.vital.sign"].create(
            {
                "encounter_id": encounter.id,
                "measured_at": datetime.now(),
                "systolic_bp": 120,
                "diastolic_bp": 80,
                "heart_rate": 72,
                "temperature": 36.6,
                "spo2": 98,
                "weight_kg": 70,
                "height_cm": 175,
            }
        )

    def test_01_draft_to_in_progress(self):
        enc = self._make_encounter()
        enc.action_start()
        self.assertEqual(enc.state, "in_progress")

    def test_02_done_requires_complaint(self):
        enc = self._make_encounter(complaint="")
        enc.action_start()
        self._add_vitals(enc)
        with self.assertRaises(
            UserError, msg="Should require chief_complaint before done"
        ):
            enc.action_done()

    def test_03_done_requires_vitals(self):
        enc = self._make_encounter()
        enc.action_start()
        # No vitals added
        with self.assertRaises(
            UserError, msg="Should require vitals before done"
        ):
            enc.action_done()

    def test_04_done_success(self):
        enc = self._make_encounter()
        enc.action_start()
        self._add_vitals(enc)
        enc.action_done()
        self.assertEqual(enc.state, "done")

    def test_05_invoice_creates_account_move(self):
        enc = self._make_encounter()
        enc.action_start()
        self._add_vitals(enc)
        enc.action_done()
        action = enc.action_invoice()
        invoice = self.env["account.move"].browse(action.get("res_id"))
        self.assertTrue(invoice.exists())
        self.assertEqual(invoice.move_type, "out_invoice")
        self.assertEqual(enc.state, "invoiced")

    def test_06_invoice_no_product_raises(self):
        """Specialty without a consultation product → UserError."""
        specialty2 = self.env["health.specialty"].create(
            {"name": "Specialty No Product / تخصص بلا منتج", "code": "XNP"}
        )
        doctor2 = self.env["res.partner"].create(
            {
                "name": "Dr. NoProduct / د. بلا منتج",
                "is_doctor": True,
                "specialty_id": specialty2.id,
            }
        )
        enc = self.env["health.encounter"].create(
            {
                "patient_id": self.patient.id,
                "doctor_id": doctor2.id,
                "chief_complaint": "Test",
            }
        )
        enc.action_start()
        self._add_vitals(enc)
        enc.action_done()
        with self.assertRaises(UserError):
            enc.action_invoice()


@tagged("post_install", "-at_install", "quinze", "quinze_clinic")
class TestHealthPrescription(TransactionCase):
    """health.prescription: state machine, expiry, qty_to_dispense."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        doctor_partner = cls.env["res.partner"].create(
            {"name": "Dr. Rx / د. وصفة", "is_doctor": True}
        )
        patient_partner = cls.env["res.partner"].create(
            {
                "name": "Rx Patient / مريض الوصفة",
                "is_patient": True,
                "national_id": "9771231234",
            }
        )
        cls.patient = cls.env["health.patient"].create(
            {"partner_id": patient_partner.id}
        )
        cls.doctor = doctor_partner
        cls.uom_tablet = cls.env["uom.uom"].search(
            [("name", "=", "Tablet")], limit=1
        ) or cls.env["uom.uom"].create(
            {
                "name": "Tablet",
                "category_id": cls.env.ref(
                    "uom.product_uom_categ_unit"
                ).id,
            }
        )
        cls.med_product = cls.env["product.product"].create(
            {
                "name": "Paracetamol 500mg",
                "type": "consu",
            }
        )

    def _make_rx(self, valid_until=None):
        rx = self.env["health.prescription"].create(
            {
                "patient_id": self.patient.id,
                "doctor_id": self.doctor.id,
                "prescription_date": date.today(),
                "valid_until": valid_until or (date.today() + timedelta(days=30)),
            }
        )
        return rx

    def _add_line(self, rx, dose=1.0, freq="bd", duration=7):
        self.env["health.prescription.line"].create(
            {
                "prescription_id": rx.id,
                "product_id": self.med_product.id,
                "dose": dose,
                "dose_uom_id": self.uom_tablet.id,
                "frequency": freq,
                "duration_days": duration,
                "route": "oral",
            }
        )

    def test_01_confirm_requires_line(self):
        rx = self._make_rx()
        with self.assertRaises(
            UserError, msg="Should require at least one line before confirm"
        ):
            rx.action_confirm()

    def test_02_confirm_with_line(self):
        rx = self._make_rx()
        self._add_line(rx)
        rx.action_confirm()
        self.assertEqual(rx.state, "confirmed")

    def test_03_prescription_number_assigned(self):
        rx = self._make_rx()
        self.assertTrue(rx.prescription_number.startswith("RX/"))

    def test_04_is_expired_false(self):
        rx = self._make_rx(valid_until=date.today() + timedelta(days=10))
        self.assertFalse(rx.is_expired)

    def test_05_is_expired_true(self):
        rx = self._make_rx(valid_until=date.today() - timedelta(days=1))
        # Force recompute
        rx._compute_is_expired()
        self.assertTrue(rx.is_expired)

    def test_06_qty_to_dispense_bd_7days(self):
        """BD × 1 tablet × 7 days = 14 tablets."""
        rx = self._make_rx()
        self._add_line(rx, dose=1.0, freq="bd", duration=7)
        line = rx.prescription_line_ids[0]
        # BD = 2 times/day → 1 × 2 × 7 = 14
        self.assertAlmostEqual(line.qty_to_dispense, 14.0, places=1)

    def test_07_cancel_and_reset(self):
        rx = self._make_rx()
        self._add_line(rx)
        rx.action_confirm()
        rx.action_cancel()
        self.assertEqual(rx.state, "cancelled")
        rx.action_reset_draft()
        self.assertEqual(rx.state, "draft")

    def test_08_line_count(self):
        rx = self._make_rx()
        self._add_line(rx)
        self._add_line(rx)
        self.assertEqual(rx.line_count, 2)


@tagged("post_install", "-at_install", "quinze", "quinze_clinic")
class TestHealthLabRequest(TransactionCase):
    """health.lab.request: state machine and bridge hook."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        doctor_partner = cls.env["res.partner"].create(
            {"name": "Dr. Lab / د. مختبر", "is_doctor": True}
        )
        patient_partner = cls.env["res.partner"].create(
            {
                "name": "Lab Patient / مريض المختبر",
                "is_patient": True,
                "national_id": "9661231234",
            }
        )
        cls.patient = cls.env["health.patient"].create(
            {"partner_id": patient_partner.id}
        )
        cls.doctor = doctor_partner
        cls.encounter = cls.env["health.encounter"].create(
            {
                "patient_id": cls.patient.id,
                "doctor_id": cls.doctor.id,
                "chief_complaint": "Lab workup / فحوصات مختبر",
            }
        )

    def _make_req(self):
        return self.env["health.lab.request"].create(
            {
                "encounter_id": self.encounter.id,
                "request_date": date.today(),
                "tests_description": "CBC, CMP / صورة دم كاملة",
                "priority": "0",
            }
        )

    def test_01_request_number_assigned(self):
        req = self._make_req()
        self.assertTrue(req.request_number.startswith("LRQ/"))

    def test_02_confirm(self):
        req = self._make_req()
        req.action_confirm()
        self.assertEqual(req.state, "confirmed")

    def test_03_cancel_and_reset(self):
        req = self._make_req()
        req.action_confirm()
        req.action_cancel()
        self.assertEqual(req.state, "cancelled")
        req.action_reset_draft()
        self.assertEqual(req.state, "draft")

    def test_04_patient_doctor_from_encounter(self):
        """patient_id and doctor_id are related from encounter."""
        req = self._make_req()
        self.assertEqual(req.patient_id, self.patient)
        self.assertEqual(req.doctor_id, self.doctor)

    def test_05_bridge_hook_noop_in_clinic(self):
        """_action_create_lab_order() is a no-op in clinic module (returns None)."""
        req = self._make_req()
        result = req._action_create_lab_order()
        self.assertIsNone(
            result,
            "_action_create_lab_order should return None when lab module not installed",
        )


@tagged("post_install", "-at_install", "quinze", "quinze_clinic")
class TestEndToEndClinicWorkflow(TransactionCase):
    """
    End-to-end test: Appointment → Encounter → Vitals → Prescription → Lab Request
    سيناريو متكامل: موعد → زيارة → علامات حيوية → وصفة → طلب مختبر
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        specialty = cls.env["health.specialty"].create(
            {"name": "Internal Medicine / طب باطني", "code": "IM"}
        )
        product = cls.env["product.template"].create(
            {
                "name": "IM Consultation",
                "type": "service",
                "list_price": 250.0,
                "sale_ok": True,
            }
        )
        specialty.consultation_product_id = product.product_variant_id

        doctor_partner = cls.env["res.partner"].create(
            {
                "name": "Dr. E2E / د. متكامل",
                "is_doctor": True,
                "specialty_id": specialty.id,
            }
        )
        patient_partner = cls.env["res.partner"].create(
            {
                "name": "E2E Patient / مريض متكامل",
                "is_patient": True,
                "national_id": "9551231234",
            }
        )
        cls.patient = cls.env["health.patient"].create(
            {"partner_id": patient_partner.id}
        )
        cls.doctor = doctor_partner
        cls.room = cls.env["health.room"].create(
            {"name": "E2E Room", "code": "E2E", "room_type": "clinic"}
        )
        cls.uom_tablet = cls.env["uom.uom"].search(
            [("name", "=", "Tablet")], limit=1
        ) or cls.env["uom.uom"].create(
            {
                "name": "Tablet",
                "category_id": cls.env.ref("uom.product_uom_categ_unit").id,
            }
        )
        cls.med = cls.env["product.product"].create(
            {"name": "Amoxicillin 500mg", "type": "consu"}
        )

    def test_full_workflow(self):
        # 1. Create and confirm appointment
        t_start = datetime.now().replace(
            hour=14, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        apt = self.env["health.appointment"].create(
            {
                "patient_id": self.patient.id,
                "doctor_id": self.doctor.id,
                "start_datetime": t_start,
                "stop_datetime": t_start + timedelta(minutes=30),
                "appointment_type": "new",
                "room_id": self.room.id,
                "chief_complaint": "Sore throat / التهاب الحلق",
            }
        )
        apt.action_confirm()
        apt.action_arrive()

        # 2. Open encounter
        apt.action_open_encounter()
        enc = apt.encounter_id
        self.assertTrue(enc.exists())

        # 3. Add vitals
        self.env["health.vital.sign"].create(
            {
                "encounter_id": enc.id,
                "measured_at": datetime.now(),
                "systolic_bp": 118,
                "diastolic_bp": 76,
                "heart_rate": 78,
                "temperature": 37.5,
                "spo2": 99,
                "weight_kg": 65,
                "height_cm": 168,
            }
        )

        # 4. Write chief complaint and complete
        enc.chief_complaint = "Sore throat, fever / التهاب الحلق والحمى"
        enc.action_done()
        self.assertEqual(enc.state, "done")

        # 5. Create prescription
        rx = self.env["health.prescription"].create(
            {
                "patient_id": self.patient.id,
                "doctor_id": self.doctor.id,
                "encounter_id": enc.id,
                "prescription_date": date.today(),
                "valid_until": date.today() + timedelta(days=7),
            }
        )
        self.env["health.prescription.line"].create(
            {
                "prescription_id": rx.id,
                "product_id": self.med.id,
                "dose": 1.0,
                "dose_uom_id": self.uom_tablet.id,
                "frequency": "tds",
                "duration_days": 7,
                "route": "oral",
                "instructions": "After meals / بعد الطعام",
            }
        )
        rx.action_confirm()
        self.assertEqual(rx.state, "confirmed")

        # 6. Create lab request
        req = self.env["health.lab.request"].create(
            {
                "encounter_id": enc.id,
                "request_date": date.today(),
                "tests_description": "Throat culture / مزرعة الحلق",
                "priority": "0",
            }
        )
        req.action_confirm()
        self.assertEqual(req.state, "confirmed")

        # 7. Invoice
        action = enc.action_invoice()
        invoice = self.env["account.move"].browse(action.get("res_id"))
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(enc.state, "invoiced")

        # 8. Verify smart button counts on patient
        self.patient.invalidate_recordset()
        self.assertGreaterEqual(self.patient.encounter_count, 1)
        self.assertGreaterEqual(self.patient.prescription_count, 1)
