# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
pharmacy.insurance.claim — Insurance Claim
============================================
مطالبة التأمين الطبي

Tracks a reimbursement claim submitted to an insurer for a dispensing.

State machine:
    draft → submitted → approved / rejected
                      ↘ (partial approval also supported)

دورة الحياة:
    مسودة → مُقدَّمة → موافق عليها / مرفوضة
                     ↘ (الموافقة الجزئية مدعومة أيضاً)
"""

from odoo import api, fields, models
from odoo.exceptions import UserError


class PharmacyInsuranceClaim(models.Model):
    _name = "pharmacy.insurance.claim"
    _description = "Insurance Claim / مطالبة تأمين"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "submission_date desc, id desc"
    _rec_name = "claim_number"

    # ── Identity ──────────────────────────────────────────────────────────────
    claim_number = fields.Char(
        string="Claim No. / رقم المطالبة",
        readonly=True,
        copy=False,
        default="New",
        index=True,
    )

    # ── Links ─────────────────────────────────────────────────────────────────
    dispensing_id = fields.Many2one(
        comodel_name="pharmacy.dispensing",
        string="Dispensing / سجل الصرف",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    patient_id = fields.Many2one(
        comodel_name="health.patient",
        string="Patient / المريض",
        related="dispensing_id.patient_id",
        store=True,
        readonly=True,
    )

    # ── Insurance details ─────────────────────────────────────────────────────
    insurer_name = fields.Char(
        string="Insurance Company / شركة التأمين",
        required=True,
        tracking=True,
    )
    policy_number = fields.Char(
        string="Policy No. / رقم البوليصة",
        tracking=True,
    )
    member_id = fields.Char(
        string="Member ID / رقم العضو",
        tracking=True,
    )
    approval_number = fields.Char(
        string="Approval No. / رقم الموافقة",
        tracking=True,
    )

    # ── Financials ────────────────────────────────────────────────────────────
    amount_claimed = fields.Monetary(
        string="Amount Claimed / المبلغ المطالب به",
        currency_field="currency_id",
        tracking=True,
    )
    coverage_pct = fields.Float(
        string="Coverage % / نسبة التغطية",
        digits=(5, 2),
        default=80.0,
        help="Percentage covered by the insurer / نسبة ما يغطيه التأمين",
        tracking=True,
    )
    amount_covered = fields.Monetary(
        string="Covered Amount / المبلغ المغطى",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_patient = fields.Monetary(
        string="Patient Share / حصة المريض",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_approved = fields.Monetary(
        string="Approved Amount / المبلغ المعتمد",
        currency_field="currency_id",
        tracking=True,
        help="Actual amount approved by the insurer after review / "
             "المبلغ الفعلي الذي وافق عليه التأمين بعد المراجعة",
    )
    currency_id = fields.Many2one(
        related="dispensing_id.currency_id",
        readonly=True,
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    submission_date = fields.Date(
        string="Submission Date / تاريخ التقديم",
        tracking=True,
    )
    response_date = fields.Date(
        string="Response Date / تاريخ الرد",
        tracking=True,
    )

    # ── Rejection / notes ────────────────────────────────────────────────────
    rejection_reason = fields.Text(
        string="Rejection Reason / سبب الرفض",
        tracking=True,
    )
    notes = fields.Text(
        string="Notes / ملاحظات",
    )

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ("draft", "Draft / مسودة"),
            ("submitted", "Submitted / مُقدَّمة"),
            ("approved", "Approved / موافق عليها"),
            ("partial", "Partially Approved / موافقة جزئية"),
            ("rejected", "Rejected / مرفوضة"),
        ],
        string="State / الحالة",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )

    # ── Sequence ──────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("claim_number", "New") == "New":
                vals["claim_number"] = (
                    self.env["ir.sequence"].next_by_code(
                        "pharmacy.insurance.claim"
                    )
                    or "CLM/000001"
                )
        return super().create(vals_list)

    # ── Computes ──────────────────────────────────────────────────────────────
    @api.depends("amount_claimed", "coverage_pct")
    def _compute_amounts(self) -> None:
        """Calculate covered and patient-share amounts.
        حساب المبلغ المغطى وحصة المريض.
        """
        for rec in self:
            covered = rec.amount_claimed * (rec.coverage_pct / 100.0)
            rec.amount_covered = covered
            rec.amount_patient = rec.amount_claimed - covered

    # ── State actions ─────────────────────────────────────────────────────────
    def action_submit(self):
        """Submit the claim to the insurer / تقديم المطالبة للتأمين."""
        for rec in self.filtered(lambda c: c.state == "draft"):
            if not rec.insurer_name:
                raise UserError(
                    "Please enter the insurance company name. / "
                    "الرجاء إدخال اسم شركة التأمين."
                )
            rec.write(
                {
                    "state": "submitted",
                    "submission_date": fields.Date.today(),
                }
            )

    def action_approve(self):
        """Mark claim as approved / قبول المطالبة."""
        for rec in self.filtered(lambda c: c.state == "submitted"):
            rec.write(
                {
                    "state": "approved",
                    "response_date": fields.Date.today(),
                    "amount_approved": rec.amount_covered
                    if not rec.amount_approved
                    else rec.amount_approved,
                }
            )
            # Credit note on the invoice for the covered portion
            if rec.dispensing_id.invoice_id:
                rec._apply_insurance_credit()

    def action_partial_approve(self):
        """Mark claim as partially approved / قبول جزئي للمطالبة."""
        for rec in self.filtered(lambda c: c.state == "submitted"):
            rec.write(
                {
                    "state": "partial",
                    "response_date": fields.Date.today(),
                }
            )

    def action_reject(self):
        """Mark claim as rejected / رفض المطالبة."""
        for rec in self.filtered(lambda c: c.state == "submitted"):
            if not rec.rejection_reason:
                raise UserError(
                    "Please enter the rejection reason. / "
                    "الرجاء إدخال سبب الرفض."
                )
            rec.write(
                {
                    "state": "rejected",
                    "response_date": fields.Date.today(),
                }
            )

    def action_reset_draft(self):
        """Reset to draft / إعادة للمسودة."""
        for rec in self.filtered(
            lambda c: c.state in ("submitted", "rejected")
        ):
            rec.state = "draft"

    # ── Private helpers ───────────────────────────────────────────────────────
    def _apply_insurance_credit(self):
        """Create a credit note on the invoice for the approved insurance amount.
        إنشاء إشعار دائن على الفاتورة بالمبلغ المعتمد من التأمين.
        """
        self.ensure_one()
        invoice = self.dispensing_id.invoice_id
        if not invoice or invoice.state != "posted":
            return
        # Create a credit note (reversal) for the covered portion
        credit_note = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "partner_id": invoice.partner_id.id,
                "invoice_date": fields.Date.today(),
                "invoice_origin": f"{invoice.name} - Insurance / تأمين",
                "company_id": invoice.company_id.id,
                "ref": f"Insurance: {self.insurer_name} — {self.claim_number}",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": (
                                f"Insurance Coverage / تغطية التأمين "
                                f"({self.insurer_name})"
                            ),
                            "quantity": 1.0,
                            "price_unit": self.amount_approved or self.amount_covered,
                        },
                    )
                ],
            }
        )
        credit_note.action_post()
        self.message_post(
            body=(
                f"Credit note {credit_note.name} created for insurance coverage. / "
                f"تم إنشاء إشعار دائن {credit_note.name} لتغطية التأمين."
            )
        )
