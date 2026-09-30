# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
lab.order.line — Individual Test within a Lab Order
=====================================================
بند الفحص ضمن أمر المختبر

Each line represents one test to be performed.
When a numeric result is entered, it is automatically compared to the
test's reference range (using the patient's gender) and flagged accordingly.

كل بند يمثل فحصاً واحداً مطلوباً.
عند إدخال نتيجة رقمية تُقارن تلقائياً بالنطاق المرجعي
(حسب جنس المريض) وتُحدَّد علامة الشذوذ.

Flags:
    normal        — within reference range
    high          — above reference high
    low           — below reference low
    critical_high — above critical high (panic value)
    critical_low  — below critical low  (panic value)
"""

from odoo import api, fields, models


# ── Flag selection ──────────────────────────────────────────────────────────
FLAG_SELECTION = [
    ("normal", "Normal / طبيعي"),
    ("high", "High ↑ / مرتفع"),
    ("low", "Low ↓ / منخفض"),
    ("critical_high", "Critical High ↑↑ / حرج مرتفع"),
    ("critical_low", "Critical Low ↓↓ / حرج منخفض"),
]


class LabOrderLine(models.Model):
    _name = "lab.order.line"
    _description = "Lab Order Line / بند أمر المختبر"
    _order = "sequence, id"

    # ── Parent ────────────────────────────────────────────────────────────────
    order_id = fields.Many2one(
        comodel_name="lab.order",
        string="Order / الأمر",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)

    # ── Test reference ────────────────────────────────────────────────────────
    test_id = fields.Many2one(
        comodel_name="lab.test",
        string="Test / الفحص",
        required=True,
        ondelete="restrict",
    )
    test_name_ar = fields.Char(
        related="test_id.name_ar",
        string="Arabic Name / الاسم بالعربية",
        readonly=True,
    )
    result_type = fields.Selection(
        related="test_id.result_type",
        readonly=True,
    )
    result_uom = fields.Char(
        related="test_id.result_uom",
        readonly=True,
        string="Unit / الوحدة",
    )

    # ── Reference range (copied from test at line creation) ───────────────────
    ref_low = fields.Float(
        string="Ref Low",
        digits=(10, 4),
        readonly=True,
    )
    ref_high = fields.Float(
        string="Ref High",
        digits=(10, 4),
        readonly=True,
    )
    ref_display = fields.Char(
        string="Reference Range / النطاق المرجعي",
        compute="_compute_ref_display",
        store=False,
    )

    # ── Results ───────────────────────────────────────────────────────────────
    result_value = fields.Float(
        string="Result / النتيجة",
        digits=(10, 4),
        tracking=True,
    )
    result_text = fields.Char(
        string="Text Result / النتيجة النصية",
        tracking=True,
    )
    result_bool = fields.Selection(
        selection=[
            ("positive", "Positive / إيجابي"),
            ("negative", "Negative / سلبي"),
        ],
        string="Pos/Neg",
        tracking=True,
    )
    flag = fields.Selection(
        selection=FLAG_SELECTION,
        string="Flag / العلامة",
        compute="_compute_flag",
        store=True,
        readonly=True,
    )
    technician_note = fields.Text(
        string="Technician Note / ملاحظة الفني",
    )
    resulted_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Resulted By / أدخل النتيجة",
        readonly=True,
        copy=False,
    )
    resulted_at = fields.Datetime(
        string="Resulted At / وقت النتيجة",
        readonly=True,
        copy=False,
    )

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ("pending", "Pending / معلق"),
            ("in_progress", "In Progress / جارٍ"),
            ("resulted", "Resulted / نتيجة جاهزة"),
        ],
        string="State",
        default="pending",
        tracking=True,
        copy=False,
    )

    # ── Onchange: populate reference range when test is selected ──────────────
    @api.onchange("test_id")
    def _onchange_test_id(self):
        """Load gender-specific reference range from the selected test.
        تحميل النطاق المرجعي الخاص بالجنس من الفحص المحدد.
        """
        if not self.test_id:
            return
        gender = "other"
        if self.order_id and self.order_id.patient_id:
            gender = self.order_id.patient_id.gender or "other"
        low, high = self.test_id.get_reference_range(gender)
        self.ref_low = low
        self.ref_high = high

    # ── Compute: flag based on result vs reference range ──────────────────────
    @api.depends(
        "result_value",
        "result_type",
        "ref_low",
        "ref_high",
        "test_id.critical_low",
        "test_id.critical_high",
    )
    def _compute_flag(self) -> None:
        """Determine the abnormality flag for numeric results.
        تحديد علامة الشذوذ للنتائج الرقمية.
        """
        for line in self:
            if line.result_type != "numeric" or not line.result_value:
                line.flag = "normal"
                continue

            v = line.result_value
            c_low = line.test_id.critical_low if line.test_id else 0.0
            c_high = line.test_id.critical_high if line.test_id else 0.0

            # Critical checks first (higher priority)
            if c_low and v < c_low:
                line.flag = "critical_low"
            elif c_high and v > c_high:
                line.flag = "critical_high"
            elif line.ref_low and v < line.ref_low:
                line.flag = "low"
            elif line.ref_high and v > line.ref_high:
                line.flag = "high"
            else:
                line.flag = "normal"

    # ── Compute: display string for reference range ───────────────────────────
    @api.depends("ref_low", "ref_high", "result_uom")
    def _compute_ref_display(self) -> None:
        for line in self:
            if line.ref_low or line.ref_high:
                low = f"{line.ref_low:.2f}" if line.ref_low else "—"
                high = f"{line.ref_high:.2f}" if line.ref_high else "—"
                uom = f" {line.result_uom}" if line.result_uom else ""
                line.ref_display = f"{low} – {high}{uom}"
            else:
                line.ref_display = "—"

    # ── Result entry ──────────────────────────────────────────────────────────
    def action_enter_result(self):
        """Finalize the result entry for this line.
        تأكيد إدخال النتيجة لهذا البند.
        """
        for line in self.filtered(lambda l: l.state != "resulted"):
            has_result = (
                line.result_value
                or line.result_text
                or line.result_bool
            )
            if has_result:
                line.write(
                    {
                        "state": "resulted",
                        "resulted_by_id": self.env.uid,
                        "resulted_at": fields.Datetime.now(),
                    }
                )
        # Trigger auto-complete on parent order
        self.mapped("order_id")._auto_complete()

    @api.model_create_multi
    def create(self, vals_list):
        """On create, populate reference range from test if not set.
        عند الإنشاء، تعبئة النطاق المرجعي من الفحص إذا لم يُحدَّد.
        """
        records = super().create(vals_list)
        for line in records:
            if line.test_id and not (line.ref_low or line.ref_high):
                gender = (
                    line.order_id.patient_id.gender
                    if line.order_id and line.order_id.patient_id
                    else "other"
                )
                low, high = line.test_id.get_reference_range(gender)
                line.write({"ref_low": low, "ref_high": high})
        return records
