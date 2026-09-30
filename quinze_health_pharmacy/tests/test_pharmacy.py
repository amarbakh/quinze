# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
test_pharmacy.py — Unit and Integration Tests for QUINZE Health Pharmacy
=========================================================================
اختبارات الوحدة والتكامل لوحدة الصيدلية

Test classes:
  TestPharmacyDrugCategory — category CRUD and constraints
  TestProductMedicationFields — is_medication, dosage_form, drug_category
  TestPharmacyDispensingExternal — external dispensing: state machine,
                                   stock picking, invoice creation
  TestPharmacyDispensingInternal — internal dispensing: prescription link,
                                   qty tracking, prescription state update
  TestPharmacyInsuranceClaim — claim state machine, coverage amounts,
                               credit note creation
  TestHealthPrescriptionExtension — dispensed_qty, remaining_qty,
                                    line_dispensing_state on Rx lines
  TestEndToEndPharmacyWorkflow — full prescription → dispensing → invoice
                                  → insurance claim scenario
"""

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "quinze", "quinze_pharmacy")
class TestPharmacyDrugCategory(TransactionCase):
    """Tests for pharmacy.drug.category / اختبارات تصنيف الأدوية."""

    def setUp(self):
        super().setUp()
        self.Category = self.env["pharmacy.drug.category"]

    def test_01_create_category(self):
        """Category can be created with name, name_ar, and code."""
        cat = self.Category.create({
            "name": "Test Analgesics",
            "name_ar": "مسكنات اختبار",
            "code": "TST",
        })
        self.assertTrue(cat.id, "Category should have been created.")
        self.assertEqual(cat.code, "TST")
        self.assertTrue(cat.active)

    def test_02_product_count_compute(self):
        """product_count reflects the number of medication products."""
        cat = self.Category.create({"name": "Count Test", "code": "CNT"})
        # Initially 0
        self.assertEqual(cat.product_count, 0)
        # Add a product
        self.env["product.template"].create({
            "name": "Test Drug",
            "is_medication": True,
            "drug_category_id": cat.id,
            "type": "consu",
        })
        self.assertEqual(cat.product_count, 1)


@tagged("post_install", "-at_install", "quinze", "quinze_pharmacy")
class TestProductMedicationFields(TransactionCase):
    """Tests for medication extension on product.template."""

    def _create_medication(self, **kwargs):
        defaults = {
            "name": "Demo Med",
            "type": "consu",
            "is_medication": True,
            "dosage_form": "tablet",
            "strength": "100 mg",
        }
        defaults.update(kwargs)
        return self.env["product.template"].create(defaults)

    def test_01_is_medication_default_false(self):
        """Non-medication products have is_medication=False by default."""
        prod = self.env["product.template"].create({
            "name": "Office Supply",
            "type": "consu",
        })
        self.assertFalse(prod.is_medication)

    def test_02_medication_fields_stored(self):
        """Medication-specific fields are stored correctly."""
        cat = self.env["pharmacy.drug.category"].create({
            "name": "Analgesics Test",
            "code": "AT1",
        })
        med = self._create_medication(
            name="Ibuprofen 400mg",
            drug_category_id=cat.id,
            generic_name_ar="إيبوبروفين 400 ملغ",
            requires_cold_chain=False,
            is_controlled=False,
        )
        self.assertEqual(med.dosage_form, "tablet")
        self.assertEqual(med.strength, "100 mg")
        self.assertEqual(med.drug_category_id.id, cat.id)
        self.assertEqual(med.generic_name_ar, "إيبوبروفين 400 ملغ")

    def test_03_controlled_substance_flag(self):
        """is_controlled flag is stored and retrievable."""
        med = self._create_medication(
            name="Tramadol 50mg",
            is_controlled=True,
        )
        self.assertTrue(med.is_controlled)


@tagged("post_install", "-at_install", "quinze", "quinze_pharmacy")
class TestPharmacyDispensingExternal(TransactionCase):
    """Tests for external (walk-in) dispensing workflow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a medication product
        cls.med = cls.env["product.template"].create({
            "name": "Ext Test Med",
            "type": "consu",
            "is_medication": True,
            "list_price": 5.0,
        })
        cls.med_variant = cls.med.product_variant_id
        # Create a partner
        cls.partner = cls.env["res.partner"].create({
            "name": "External Walk-in Patient",
        })

    def _make_dispensing(self, **kwargs):
        disp = self.env["pharmacy.dispensing"].create({
            "dispensing_type": "external",
            "partner_id": self.partner.id,
            "line_ids": [(0, 0, {
                "product_id": self.med_variant.id,
                "qty_dispensed": 10.0,
                "price_unit": 5.0,
            })],
            **kwargs,
        })
        return disp

    def test_01_sequence_assigned(self):
        """dispensing_number is assigned on create."""
        disp = self._make_dispensing()
        self.assertNotEqual(disp.dispensing_number, "New")
        self.assertTrue(disp.dispensing_number.startswith("DIS"))

    def test_02_state_draft_on_create(self):
        """New dispensing starts in draft state."""
        disp = self._make_dispensing()
        self.assertEqual(disp.state, "draft")

    def test_03_confirm_creates_stock_picking(self):
        """action_confirm creates a stock.picking."""
        disp = self._make_dispensing()
        disp.action_confirm()
        self.assertEqual(disp.state, "confirmed")
        self.assertTrue(disp.picking_id, "Picking should be created on confirm.")

    def test_04_confirm_creates_invoice_for_external(self):
        """action_confirm creates a draft invoice for external dispensing."""
        disp = self._make_dispensing()
        disp.action_confirm()
        self.assertTrue(
            disp.invoice_id,
            "Invoice should be created for external dispensing."
        )
        self.assertEqual(disp.invoice_id.move_type, "out_invoice")
        self.assertEqual(disp.invoice_id.state, "draft")

    def test_05_no_partner_raises_error(self):
        """Confirming an external dispensing without partner raises UserError."""
        disp = self.env["pharmacy.dispensing"].create({
            "dispensing_type": "external",
            "line_ids": [(0, 0, {
                "product_id": self.med_variant.id,
                "qty_dispensed": 5.0,
                "price_unit": 5.0,
            })],
        })
        with self.assertRaises(UserError):
            disp.action_confirm()

    def test_06_no_lines_raises_error(self):
        """Confirming a dispensing without lines raises UserError."""
        disp = self.env["pharmacy.dispensing"].create({
            "dispensing_type": "external",
            "partner_id": self.partner.id,
        })
        with self.assertRaises(UserError):
            disp.action_confirm()

    def test_07_amount_total_computed(self):
        """amount_total = sum of line subtotals."""
        disp = self._make_dispensing()
        # 10 × 5.0 = 50.0
        self.assertAlmostEqual(disp.amount_total, 50.0, places=2)

    def test_08_cancel_from_confirmed(self):
        """action_cancel from confirmed moves to cancelled."""
        disp = self._make_dispensing()
        disp.action_confirm()
        disp.action_cancel()
        self.assertEqual(disp.state, "cancelled")

    def test_09_reset_draft_from_cancelled(self):
        """action_reset_draft moves cancelled back to draft."""
        disp = self._make_dispensing()
        disp.action_confirm()
        disp.action_cancel()
        disp.action_reset_draft()
        self.assertEqual(disp.state, "draft")


@tagged("post_install", "-at_install", "quinze", "quinze_pharmacy")
class TestPharmacyDispensingInternal(TransactionCase):
    """Tests for internal dispensing linked to a clinic prescription."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))
        # Create medication
        cls.med_tmpl = cls.env["product.template"].create({
            "name": "Internal Test Med",
            "type": "consu",
            "is_medication": True,
            "list_price": 3.0,
        })
        cls.med = cls.med_tmpl.product_variant_id
        # Create patient partner
        cls.partner = cls.env["res.partner"].create({
            "name": "Internal Test Patient",
        })
        # Create health.patient
        cls.patient = cls.env["health.patient"].create({
            "partner_id": cls.partner.id,
        })
        # Create doctor partner
        cls.doctor = cls.env["res.partner"].create({
            "name": "Dr. Test",
            "is_doctor": True,
        })
        # Create a confirmed prescription
        cls.rx = cls.env["health.prescription"].create({
            "patient_id": cls.patient.id,
            "doctor_id": cls.doctor.id,
            "state": "confirmed",
        })
        # Create prescription lines
        cls.rx_line = cls.env["health.prescription.line"].create({
            "prescription_id": cls.rx.id,
            "product_id": cls.med.id,
            "dose": 1.0,
            "frequency": "od",
            "duration_days": 30,
        })

    def test_01_internal_dispensing_no_invoice(self):
        """Internal dispensing does NOT create an invoice on confirm."""
        disp = self.env["pharmacy.dispensing"].create({
            "dispensing_type": "internal",
            "prescription_id": self.rx.id,
            "patient_id": self.patient.id,
            "partner_id": self.partner.id,
            "line_ids": [(0, 0, {
                "product_id": self.med.id,
                "prescription_line_id": self.rx_line.id,
                "qty_ordered": 30.0,
                "qty_dispensed": 30.0,
                "price_unit": 3.0,
            })],
        })
        disp.action_confirm()
        self.assertFalse(
            disp.invoice_id,
            "Internal dispensing should NOT create an invoice."
        )
        self.assertTrue(
            disp.picking_id,
            "Internal dispensing should still create a stock picking."
        )

    def test_02_dispense_updates_prescription_line_qty(self):
        """Completing dispensing updates dispensed_qty on the prescription line."""
        disp = self.env["pharmacy.dispensing"].create({
            "dispensing_type": "internal",
            "prescription_id": self.rx.id,
            "patient_id": self.patient.id,
            "partner_id": self.partner.id,
            "line_ids": [(0, 0, {
                "product_id": self.med.id,
                "prescription_line_id": self.rx_line.id,
                "qty_ordered": 30.0,
                "qty_dispensed": 15.0,
                "price_unit": 3.0,
            })],
        })
        disp.action_confirm()
        disp.action_dispense()
        self.assertAlmostEqual(
            self.rx_line.dispensed_qty, 15.0, places=2,
            msg="dispensed_qty should be updated on Rx line."
        )
        self.assertEqual(self.rx_line.line_dispensing_state, "partial")

    def test_03_full_dispense_marks_prescription_dispensed(self):
        """Dispensing full qty updates prescription state to 'dispensed'."""
        # Create fresh prescription + line for isolation
        rx2 = self.env["health.prescription"].create({
            "patient_id": self.patient.id,
            "doctor_id": self.doctor.id,
            "state": "confirmed",
        })
        rx2_line = self.env["health.prescription.line"].create({
            "prescription_id": rx2.id,
            "product_id": self.med.id,
            "dose": 1.0,
            "frequency": "od",
            "duration_days": 7,
        })
        disp = self.env["pharmacy.dispensing"].create({
            "dispensing_type": "internal",
            "prescription_id": rx2.id,
            "patient_id": self.patient.id,
            "partner_id": self.partner.id,
            "line_ids": [(0, 0, {
                "product_id": self.med.id,
                "prescription_line_id": rx2_line.id,
                "qty_ordered": rx2_line.qty_to_dispense,
                "qty_dispensed": rx2_line.qty_to_dispense,
                "price_unit": 3.0,
            })],
        })
        disp.action_confirm()
        disp.action_dispense()
        self.assertEqual(rx2_line.line_dispensing_state, "dispensed")
        self.assertEqual(rx2.state, "dispensed")

    def test_04_dispensing_count_on_prescription(self):
        """dispensing_count on prescription increments correctly."""
        initial = self.rx.dispensing_count
        self.env["pharmacy.dispensing"].create({
            "dispensing_type": "internal",
            "prescription_id": self.rx.id,
            "patient_id": self.patient.id,
            "partner_id": self.partner.id,
            "line_ids": [(0, 0, {
                "product_id": self.med.id,
                "qty_dispensed": 10.0,
                "price_unit": 3.0,
            })],
        })
        self.assertEqual(self.rx.dispensing_count, initial + 1)


@tagged("post_install", "-at_install", "quinze", "quinze_pharmacy")
class TestPharmacyInsuranceClaim(TransactionCase):
    """Tests for pharmacy.insurance.claim state machine and amounts."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))
        # Build a dispensed dispensing to attach claims to
        med_tmpl = cls.env["product.template"].create({
            "name": "Claim Test Med",
            "type": "consu",
            "is_medication": True,
            "list_price": 10.0,
        })
        med = med_tmpl.product_variant_id
        partner = cls.env["res.partner"].create({"name": "Claim Patient"})
        disp = cls.env["pharmacy.dispensing"].create({
            "dispensing_type": "external",
            "partner_id": partner.id,
            "line_ids": [(0, 0, {
                "product_id": med.id,
                "qty_dispensed": 30.0,
                "price_unit": 10.0,
            })],
        })
        disp.action_confirm()
        disp.action_dispense()
        cls.dispensing = disp
        cls.Claim = cls.env["pharmacy.insurance.claim"]

    def _make_claim(self, **kwargs):
        defaults = {
            "dispensing_id": self.dispensing.id,
            "insurer_name": "National Insurance Co.",
            "amount_claimed": 300.0,
            "coverage_pct": 80.0,
        }
        defaults.update(kwargs)
        return self.Claim.create(defaults)

    def test_01_sequence_assigned(self):
        """claim_number is assigned from sequence on create."""
        claim = self._make_claim()
        self.assertNotEqual(claim.claim_number, "New")
        self.assertTrue(claim.claim_number.startswith("CLM"))

    def test_02_state_draft_on_create(self):
        """New claim starts in draft."""
        claim = self._make_claim()
        self.assertEqual(claim.state, "draft")

    def test_03_amount_computation(self):
        """amount_covered and amount_patient are computed correctly."""
        claim = self._make_claim(amount_claimed=300.0, coverage_pct=80.0)
        self.assertAlmostEqual(claim.amount_covered, 240.0, places=2)
        self.assertAlmostEqual(claim.amount_patient, 60.0, places=2)

    def test_04_submit_sets_date(self):
        """action_submit transitions to submitted and sets submission_date."""
        from odoo import fields
        claim = self._make_claim()
        claim.action_submit()
        self.assertEqual(claim.state, "submitted")
        self.assertEqual(claim.submission_date, fields.Date.today())

    def test_05_submit_without_insurer_name_raises(self):
        """Submitting without insurer_name raises UserError."""
        claim = self._make_claim(insurer_name="")
        with self.assertRaises(UserError):
            claim.action_submit()

    def test_06_approve_sets_approved_amount(self):
        """action_approve sets state to approved and populates amount_approved."""
        claim = self._make_claim()
        claim.action_submit()
        claim.action_approve()
        self.assertEqual(claim.state, "approved")
        # amount_approved defaults to amount_covered when not set
        self.assertAlmostEqual(claim.amount_approved, 240.0, places=2)

    def test_07_partial_approval(self):
        """action_partial_approve sets state to partial."""
        claim = self._make_claim()
        claim.action_submit()
        claim.action_partial_approve()
        self.assertEqual(claim.state, "partial")

    def test_08_reject_requires_reason(self):
        """action_reject raises UserError when rejection_reason is empty."""
        claim = self._make_claim()
        claim.action_submit()
        with self.assertRaises(UserError):
            claim.action_reject()

    def test_09_reject_with_reason(self):
        """action_reject succeeds when rejection_reason is provided."""
        claim = self._make_claim()
        claim.action_submit()
        claim.rejection_reason = "Duplicate claim / مطالبة مكررة"
        claim.action_reject()
        self.assertEqual(claim.state, "rejected")

    def test_10_reset_to_draft(self):
        """action_reset_draft from submitted/rejected returns to draft."""
        claim = self._make_claim()
        claim.action_submit()
        claim.action_reset_draft()
        self.assertEqual(claim.state, "draft")

    def test_11_coverage_pct_zero(self):
        """0% coverage: amount_covered=0, amount_patient=amount_claimed."""
        claim = self._make_claim(coverage_pct=0.0)
        self.assertAlmostEqual(claim.amount_covered, 0.0, places=2)
        self.assertAlmostEqual(claim.amount_patient, 300.0, places=2)

    def test_12_full_coverage(self):
        """100% coverage: amount_covered = amount_claimed, amount_patient = 0."""
        claim = self._make_claim(coverage_pct=100.0)
        self.assertAlmostEqual(claim.amount_covered, 300.0, places=2)
        self.assertAlmostEqual(claim.amount_patient, 0.0, places=2)


@tagged("post_install", "-at_install", "quinze", "quinze_pharmacy")
class TestHealthPrescriptionExtension(TransactionCase):
    """Tests for pharmacy extension fields on health.prescription.line."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))
        cls.med = cls.env["product.template"].create({
            "name": "RxExt Test Med",
            "type": "consu",
            "is_medication": True,
        }).product_variant_id
        cls.partner = cls.env["res.partner"].create({"name": "RxExt Patient"})
        cls.patient = cls.env["health.patient"].create(
            {"partner_id": cls.partner.id}
        )
        cls.doctor = cls.env["res.partner"].create(
            {"name": "RxExt Doctor", "is_doctor": True}
        )

    def _make_rx(self):
        rx = self.env["health.prescription"].create({
            "patient_id": self.patient.id,
            "doctor_id": self.doctor.id,
            "state": "confirmed",
        })
        line = self.env["health.prescription.line"].create({
            "prescription_id": rx.id,
            "product_id": self.med.id,
            "dose": 1.0,
            "frequency": "bd",
            "duration_days": 5,
        })
        return rx, line

    def test_01_dispensed_qty_defaults_zero(self):
        """dispensed_qty starts at 0 on a new Rx line."""
        _rx, line = self._make_rx()
        self.assertAlmostEqual(line.dispensed_qty, 0.0, places=2)

    def test_02_line_state_pending_when_no_dispense(self):
        """line_dispensing_state is 'pending' when dispensed_qty = 0."""
        _rx, line = self._make_rx()
        self.assertEqual(line.line_dispensing_state, "pending")

    def test_03_remaining_qty_equals_qty_to_dispense(self):
        """remaining_qty = qty_to_dispense when nothing is dispensed yet."""
        _rx, line = self._make_rx()
        # BD × 1 × 5 = 10 tablets
        self.assertAlmostEqual(
            line.remaining_qty, line.qty_to_dispense, places=2
        )

    def test_04_partial_dispense_sets_partial_state(self):
        """Updating dispensed_qty to partial sets line_dispensing_state = partial."""
        _rx, line = self._make_rx()
        line.dispensed_qty = line.qty_to_dispense / 2
        self.assertEqual(line.line_dispensing_state, "partial")

    def test_05_full_dispense_sets_dispensed_state(self):
        """Setting dispensed_qty = qty_to_dispense → line_dispensing_state = dispensed."""
        _rx, line = self._make_rx()
        line.dispensed_qty = line.qty_to_dispense
        self.assertEqual(line.line_dispensing_state, "dispensed")
        self.assertAlmostEqual(line.remaining_qty, 0.0, places=2)

    def test_06_dispensing_count_starts_zero(self):
        """New prescription has dispensing_count = 0."""
        rx, _line = self._make_rx()
        self.assertEqual(rx.dispensing_count, 0)


@tagged("post_install", "-at_install", "quinze", "quinze_pharmacy")
class TestEndToEndPharmacyWorkflow(TransactionCase):
    """End-to-end test: Prescription → Dispensing → Invoice → Insurance Claim.

    اختبار شامل: وصفة → صرف → فاتورة → مطالبة تأمين
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))
        # Medication
        cls.med_tmpl = cls.env["product.template"].create({
            "name": "E2E Pharmacy Med",
            "type": "consu",
            "is_medication": True,
            "list_price": 25.0,
        })
        cls.med = cls.med_tmpl.product_variant_id
        # Patient
        cls.partner = cls.env["res.partner"].create({"name": "E2E Pharmacy Patient"})
        cls.patient = cls.env["health.patient"].create(
            {"partner_id": cls.partner.id}
        )
        cls.doctor = cls.env["res.partner"].create(
            {"name": "E2E Doctor", "is_doctor": True}
        )

    def test_full_external_dispensing_with_insurance(self):
        """
        Full workflow for external dispensing:
        1. Create dispensing (external)
        2. Confirm → verify picking + invoice created
        3. Dispense → verify invoice posted, picking done, dispensed_at set
        4. Create insurance claim → submit → approve → verify credit note
        """
        # Step 1: Create external dispensing
        disp = self.env["pharmacy.dispensing"].create({
            "dispensing_type": "external",
            "patient_id": self.patient.id,
            "partner_id": self.partner.id,
            "line_ids": [(0, 0, {
                "product_id": self.med.id,
                "qty_dispensed": 10.0,
                "price_unit": 25.0,
            })],
        })
        self.assertEqual(disp.state, "draft")
        self.assertAlmostEqual(disp.amount_total, 250.0, places=2)

        # Step 2: Confirm
        disp.action_confirm()
        self.assertEqual(disp.state, "confirmed")
        self.assertTrue(disp.picking_id, "Picking must exist after confirm.")
        self.assertTrue(disp.invoice_id, "Invoice must exist after confirm (external).")
        self.assertEqual(disp.invoice_id.state, "draft")

        # Step 3: Dispense
        disp.action_dispense()
        self.assertEqual(disp.state, "dispensed")
        self.assertTrue(disp.dispensed_at, "dispensed_at must be set.")
        self.assertEqual(
            disp.invoice_id.state, "posted",
            "Invoice should be posted after dispense."
        )

        # Step 4: Insurance claim
        claim = self.env["pharmacy.insurance.claim"].create({
            "dispensing_id": disp.id,
            "insurer_name": "Gulf Health Insurance",
            "amount_claimed": 250.0,
            "coverage_pct": 90.0,
        })
        self.assertAlmostEqual(claim.amount_covered, 225.0, places=2)
        self.assertAlmostEqual(claim.amount_patient, 25.0, places=2)

        # Submit claim
        claim.action_submit()
        self.assertEqual(claim.state, "submitted")

        # Approve claim — should create credit note
        claim.action_approve()
        self.assertEqual(claim.state, "approved")

        # Verify credit note was created
        credit_notes = self.env["account.move"].search([
            ("move_type", "=", "out_refund"),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertTrue(
            credit_notes,
            "A credit note should be created on insurance claim approval."
        )
