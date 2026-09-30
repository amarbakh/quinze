# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
lab.order — Laboratory Order
==============================
أمر المختبر

Master record for a batch of lab tests ordered for a patient.
Created automatically when health.lab.request is confirmed.

State machine:
    draft → sample_collected → in_progress → done
                                           ↘ cancelled

يُنشأ تلقائياً عند تأكيد طلب المختبر من العيادة.
دورة الحياة:
    مسودة → تم جمع العينة → جارٍ → منتهٍ
                                  ↘ ملغى
"""

from odoo import api, fields, models
from odoo.exceptions import UserError


class LabOrder(models.Model):
    _name = "lab.order"
    _description = "Lab Order / أمر مختبر"
    _inherit = ["health.mixin"]
    _order = "order_date desc, id desc"
    _rec_name = "order_number"

    # ── Identity ─────────────────────────────────────────────────────────────
    order_number = fields.Char(
        string="Order Number / رقم الأمر",
        readonly=True,
        copy=False,
        default="New",
        index=True,
    )

    # ── Links ─────────────────────────────────────────────────────────────────
    lab_request_id = fields.Many2one(
        comodel_name="health.lab.request",
        string="Lab Request / طلب المختبر",
        ondelete="restrict",
        copy=False,
        readonly=True,
        tracking=True,
    )
    encounter_id = fields.Many2one(
        comodel_name="health.encounter",
        string="Encounter / الزيارة",
        related="lab_request_id.encounter_id",
        store=True,
        readonly=True,
    )
    patient_id = fields.Many2one(
        comodel_name="health.patient",
        string="Patient / المريض",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,   # perf: searched in reports and API filters
    )
    doctor_id = fields.Many2one(
        comodel_name="res.partner",
        string="Referring Doctor / الطبيب المحيل",
        domain="[('is_doctor','=',True)]",
        tracking=True,
        index=True,
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    order_date = fields.Date(
        string="Order Date / تاريخ الأمر",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    expected_date = fields.Date(
        string="Expected Date / التاريخ المتوقع",
        tracking=True,
    )
    completed_date = fields.Datetime(
        string="Completed At / وقت الاكتمال",
        readonly=True,
        copy=False,
    )

    # ── Priority ──────────────────────────────────────────────────────────────
    priority = fields.Selection(
        selection=[
            ("0", "Normal / عادي"),
            ("1", "High / عالٍ"),
            ("2", "Urgent / عاجل"),
        ],
        string="Priority / الأولوية",
        default="0",
        tracking=True,
    )

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ("draft", "Draft / مسودة"),
            ("sample_collected", "Sample Collected / تم جمع العينة"),
            ("in_progress", "In Progress / جارٍ"),
            ("done", "Done / منتهٍ"),
            ("cancelled", "Cancelled / ملغى"),
        ],
        string="State / الحالة",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
        index=True,   # perf: heavily filtered in views and API
    )

    # ── SQL Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        (
            "order_number_company_uniq",
            "UNIQUE(order_number, company_id)",
            "Lab order number must be unique per company / رقم أمر المختبر يجب أن يكون فريداً لكل شركة",
        ),
    ]

    # ── Children ──────────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        comodel_name="lab.order.line",
        inverse_name="order_id",
        string="Tests / الفحوصات",
    )
    sample_ids = fields.One2many(
        comodel_name="lab.sample",
        inverse_name="lab_order_id",
        string="Samples / العينات",
    )

    # ── Counters (smart buttons) ──────────────────────────────────────────────
    line_count = fields.Integer(
        string="# Tests",
        compute="_compute_counts",
        store=True,
    )
    sample_count = fields.Integer(
        string="# Samples",
        compute="_compute_counts",
        store=True,
    )
    result_count = fields.Integer(
        string="# Results",
        compute="_compute_counts",
        store=True,
    )
    abnormal_count = fields.Integer(
        string="# Abnormal",
        compute="_compute_counts",
        store=True,
        help="Number of results outside normal range / عدد النتائج خارج النطاق الطبيعي",
    )
    critical_count = fields.Integer(
        string="# Critical",
        compute="_compute_counts",
        store=True,
        help="Number of critical (panic) values / عدد القيم الحرجة",
    )

    # ── Clinical indication ───────────────────────────────────────────────────
    clinical_indication = fields.Text(
        string="Clinical Indication / المؤشر السريري",
    )

    # ── Sequence ─────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        """Assign order_number from sequence on creation.
        تعيين رقم الأمر من التسلسل عند الإنشاء.
        """
        for vals in vals_list:
            if vals.get("order_number", "New") == "New":
                vals["order_number"] = self.env["ir.sequence"].next_by_code(
                    "lab.order"
                ) or "LAB/000001"
        return super().create(vals_list)

    # ── Computes ──────────────────────────────────────────────────────────────
    @api.depends("line_ids", "line_ids.flag", "sample_ids")
    def _compute_counts(self) -> None:
        """Compute all counters in one pass.
        حساب جميع العدادات في دورة واحدة.
        """
        for rec in self:
            lines = rec.line_ids
            resulted = lines.filtered(lambda l: l.result_value is not None
                                      or l.result_text or l.result_bool)
            abnormal = lines.filtered(
                lambda l: l.flag in ("high", "low", "critical_high", "critical_low")
            )
            critical = lines.filtered(
                lambda l: l.flag in ("critical_high", "critical_low")
            )
            rec.line_count = len(lines)
            rec.sample_count = len(rec.sample_ids)
            rec.result_count = len(resulted)
            rec.abnormal_count = len(abnormal)
            rec.critical_count = len(critical)

    # ── State actions ─────────────────────────────────────────────────────────
    def action_collect_sample(self):
        """Move order to sample_collected state and auto-create sample records.
        نقل الأمر لحالة 'تم جمع العينة' وإنشاء سجلات العينات تلقائياً.
        """
        for rec in self.filtered(lambda o: o.state == "draft"):
            if not rec.line_ids:
                raise UserError(
                    "Please add at least one test before collecting a sample. / "
                    "الرجاء إضافة فحص واحد على الأقل قبل جمع العينة."
                )
            # Auto-create one sample per distinct sample_type in the test lines
            needed_types = set(rec.line_ids.mapped("test_id.sample_type"))
            for stype in needed_types:
                if not rec.sample_ids.filtered(
                    lambda s: s.sample_type == stype
                ):
                    self.env["lab.sample"].create(
                        {
                            "lab_order_id": rec.id,
                            "sample_type": stype,
                            "state": "collected",
                            "collection_datetime": fields.Datetime.now(),
                            "collector_id": self.env.uid,
                        }
                    )
            rec.state = "sample_collected"

    def action_receive_samples(self):
        """Mark all pending/collected samples as received and move to in_progress.
        تسجيل استلام جميع العينات والانتقال لحالة 'جارٍ'.
        """
        for rec in self.filtered(lambda o: o.state == "sample_collected"):
            rec.sample_ids.filtered(
                lambda s: s.state in ("pending", "collected")
            ).action_receive()
            rec.state = "in_progress"

    def action_cancel(self):
        """Cancel the order / إلغاء الأمر."""
        cancelable = ("draft", "sample_collected", "in_progress")
        for rec in self.filtered(lambda o: o.state in cancelable):
            rec.state = "cancelled"

    def action_reset_draft(self):
        """Reset cancelled order to draft / إعادة الأمر الملغى للمسودة."""
        for rec in self.filtered(lambda o: o.state == "cancelled"):
            rec.state = "draft"

    def action_print_report(self):
        """Trigger the QWeb PDF lab report / طباعة تقرير المختبر PDF."""
        self.ensure_one()
        return self.env.ref(
            "quinze_health_lab.action_report_lab_order"
        ).report_action(self)

    # ── Internal helpers ──────────────────────────────────────────────────────
    def _check_samples_received(self):
        """Called by lab.sample.action_receive — moves order to in_progress
        when all samples are received.
        يُستدعى من lab.sample عند الاستلام — ينقل الأمر لحالة 'جارٍ'.
        """
        for rec in self.filtered(lambda o: o.state == "sample_collected"):
            all_received = all(
                s.state == "received"
                for s in rec.sample_ids
                if s.state != "rejected"
            )
            if all_received and rec.sample_ids:
                rec.state = "in_progress"

    def _auto_complete(self):
        """Auto-complete the order when all lines have results.
        اكتمال الأمر تلقائياً عند إدخال جميع النتائج.
        """
        for rec in self.filtered(lambda o: o.state == "in_progress"):
            if rec.line_ids and all(
                line.state == "resulted" for line in rec.line_ids
            ):
                rec.write(
                    {
                        "state": "done",
                        "completed_date": fields.Datetime.now(),
                    }
                )
                # Notify the requesting doctor via chatter
                rec.message_post(
                    body=(
                        "✅ All results are ready. / جميع النتائج جاهزة."
                    ),
                    subtype_xmlid="mail.mt_note",
                )
