# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
lab.sample — Laboratory Sample Tracking
=========================================
تتبع عينات المختبر

Tracks a physical specimen from collection through to receipt in the lab.
State machine:  pending → collected → received → rejected

يتتبع العينة الجسدية من لحظة الجمع حتى الاستلام في المختبر.
دورة الحياة: معلق → تم الجمع → تم الاستلام → مرفوض
"""

from odoo import api, fields, models
from odoo.exceptions import UserError


class LabSample(models.Model):
    _name = "lab.sample"
    _description = "Lab Sample / عينة مخبرية"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "collection_datetime desc, id desc"

    # ── Identity ─────────────────────────────────────────────────────────────
    name = fields.Char(
        string="Sample ID / رقم العينة",
        readonly=True,
        copy=False,
        default="New",
    )
    lab_order_id = fields.Many2one(
        comodel_name="lab.order",
        string="Lab Order / أمر المختبر",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    patient_id = fields.Many2one(
        comodel_name="health.patient",
        string="Patient / المريض",
        related="lab_order_id.patient_id",
        store=True,
        readonly=True,
    )

    # ── Sample details ────────────────────────────────────────────────────────
    sample_type = fields.Selection(
        selection=[
            ("blood_venous", "Venous Blood / دم وريدي"),
            ("blood_capillary", "Capillary Blood / دم شعري"),
            ("urine", "Urine / بول"),
            ("stool", "Stool / براز"),
            ("sputum", "Sputum / بلغم"),
            ("swab", "Swab / مسحة"),
            ("csf", "CSF / سائل نخاعي"),
            ("other", "Other / أخرى"),
        ],
        string="Sample Type / نوع العينة",
        required=True,
        default="blood_venous",
        tracking=True,
    )
    volume_ml = fields.Float(
        string="Volume (mL) / الحجم (مل)",
        digits=(6, 2),
    )
    container = fields.Char(
        string="Container / الحاوية",
        help="e.g. EDTA tube, Red-top tube / أنبوب EDTA، أنبوب بلا مضاد تخثر",
    )
    barcode = fields.Char(
        string="Barcode / الباركود",
        copy=False,
        index=True,
    )

    # ── Collection ────────────────────────────────────────────────────────────
    collection_datetime = fields.Datetime(
        string="Collected At / وقت الجمع",
        tracking=True,
    )
    collector_id = fields.Many2one(
        comodel_name="res.users",
        string="Collected By / جُمعت بواسطة",
        tracking=True,
    )

    # ── Receipt ───────────────────────────────────────────────────────────────
    received_datetime = fields.Datetime(
        string="Received At / وقت الاستلام",
        tracking=True,
    )
    received_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Received By / استُلمت بواسطة",
        tracking=True,
    )

    # ── Rejection ────────────────────────────────────────────────────────────
    rejection_reason = fields.Text(
        string="Rejection Reason / سبب الرفض",
    )

    # ── State ────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ("pending", "Pending / معلق"),
            ("collected", "Collected / تم الجمع"),
            ("received", "Received / تم الاستلام"),
            ("rejected", "Rejected / مرفوض"),
        ],
        string="State / الحالة",
        default="pending",
        required=True,
        tracking=True,
        copy=False,
    )

    # ── Notes ─────────────────────────────────────────────────────────────────
    note = fields.Text(string="Notes / ملاحظات")

    # ── Sequence assignment ───────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        """Assign barcode/name from sequence on creation.
        تعيين رقم العينة من التسلسل عند الإنشاء.
        """
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "lab.sample"
                ) or "SMP/000001"
        return super().create(vals_list)

    # ── State actions ─────────────────────────────────────────────────────────
    def action_collect(self):
        """Mark sample as collected / تسجيل جمع العينة."""
        for rec in self.filtered(lambda s: s.state == "pending"):
            rec.write(
                {
                    "state": "collected",
                    "collection_datetime": fields.Datetime.now(),
                    "collector_id": self.env.uid,
                }
            )

    def action_receive(self):
        """Mark sample as received in the lab / تسجيل استلام العينة في المختبر."""
        for rec in self.filtered(lambda s: s.state == "collected"):
            rec.write(
                {
                    "state": "received",
                    "received_datetime": fields.Datetime.now(),
                    "received_by_id": self.env.uid,
                }
            )
        # Trigger order to move to in_progress if all samples received
        orders = self.mapped("lab_order_id")
        for order in orders:
            order._check_samples_received()

    def action_reject(self):
        """Mark sample as rejected / تسجيل رفض العينة."""
        for rec in self.filtered(
            lambda s: s.state in ("pending", "collected")
        ):
            if not rec.rejection_reason:
                raise UserError(
                    "Please enter a rejection reason before rejecting the sample. / "
                    "الرجاء إدخال سبب الرفض قبل رفض العينة."
                )
            rec.state = "rejected"
