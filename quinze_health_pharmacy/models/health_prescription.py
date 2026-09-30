# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
health.prescription — Pharmacy Extension
==========================================
تمديد الوصفة الطبية للصيدلية

Inherits health.prescription (clinic module) to add:
  - dispensed_qty on prescription lines
  - dispensing_ids / dispensing_count on the prescription
  - _compute_dispensing_state() to update state from dispensed qtys
  - action_create_dispensing() smart button action

يرث health.prescription ليضيف:
  - كمية مصروفة على بنود الوصفة
  - ربط بسجلات الصرف
  - حساب حالة الصرف تلقائياً
"""

from odoo import api, fields, models


class HealthPrescriptionLine(models.Model):
    _inherit = "health.prescription.line"

    # ── Dispensing tracking ───────────────────────────────────────────────────
    dispensed_qty = fields.Float(
        string="Dispensed Qty / الكمية المصروفة",
        digits=(10, 2),
        default=0.0,
        readonly=True,
        copy=False,
        help="Total quantity dispensed across all dispensing records / "
             "إجمالي الكمية المصروفة في جميع سجلات الصرف",
    )
    remaining_qty = fields.Float(
        string="Remaining / المتبقية",
        compute="_compute_remaining_qty",
        store=True,
        digits=(10, 2),
    )
    line_dispensing_state = fields.Selection(
        selection=[
            ("pending", "Pending / معلق"),
            ("partial", "Partially Dispensed / جزئي"),
            ("dispensed", "Fully Dispensed / مكتمل"),
        ],
        string="Line State / حالة البند",
        compute="_compute_remaining_qty",
        store=True,
    )

    @api.depends("qty_to_dispense", "dispensed_qty")
    def _compute_remaining_qty(self) -> None:
        for line in self:
            remaining = max(0.0, line.qty_to_dispense - line.dispensed_qty)
            line.remaining_qty = remaining
            if line.dispensed_qty <= 0:
                line.line_dispensing_state = "pending"
            elif remaining > 0:
                line.line_dispensing_state = "partial"
            else:
                line.line_dispensing_state = "dispensed"


class HealthPrescription(models.Model):
    _inherit = "health.prescription"

    # ── Dispensing children ───────────────────────────────────────────────────
    dispensing_ids = fields.One2many(
        comodel_name="pharmacy.dispensing",
        inverse_name="prescription_id",
        string="Dispensings / سجلات الصرف",
    )
    dispensing_count = fields.Integer(
        string="# Dispensings",
        compute="_compute_dispensing_count",
        store=True,
    )

    # ── Compute dispensing count ──────────────────────────────────────────────
    @api.depends("dispensing_ids")
    def _compute_dispensing_count(self) -> None:
        for rec in self:
            rec.dispensing_count = len(rec.dispensing_ids)

    # ── Compute dispensing state from line states ─────────────────────────────
    def _compute_dispensing_state(self):
        """Recompute the prescription's dispensing state based on line qtys.

        Called by pharmacy.dispensing._update_prescription_state() after
        a dispensing is completed.

        يُعيد حساب حالة الصرف للوصفة بناءً على كميات بنودها.
        يُستدعى من pharmacy.dispensing بعد اكتمال سجل الصرف.
        """
        for rec in self:
            lines = rec.prescription_line_ids
            if not lines:
                continue
            all_dispensed = all(
                ln.line_dispensing_state == "dispensed" for ln in lines
            )
            any_dispensed = any(
                ln.dispensed_qty > 0 for ln in lines
            )
            if all_dispensed:
                rec.state = "dispensed"
            elif any_dispensed:
                rec.state = "partially_dispensed"
            # If none dispensed, leave state as is (confirmed)

    # ── Smart button action ───────────────────────────────────────────────────
    def action_create_dispensing(self):
        """Open a new dispensing form pre-filled from this prescription.
        فتح نموذج صرف جديد مُعبَّأ مسبقاً من هذه الوصفة.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "pharmacy.dispensing",
            "view_mode": "form",
            "context": {
                "default_dispensing_type": "internal",
                "default_prescription_id": self.id,
                "default_patient_id": self.patient_id.id,
                "default_partner_id": self.patient_id.partner_id.id
                if self.patient_id.partner_id
                else False,
            },
            "target": "current",
        }

    def action_view_dispensings(self):
        """Open the list of dispensings for this prescription.
        عرض قائمة سجلات الصرف لهذه الوصفة.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "pharmacy.dispensing",
            "view_mode": "tree,form",
            "domain": [("prescription_id", "=", self.id)],
            "context": {"default_prescription_id": self.id},
        }
