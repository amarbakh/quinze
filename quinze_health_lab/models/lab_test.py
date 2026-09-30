# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
lab.test — Laboratory Test Definition
======================================
تعريف الفحص المخبري

Holds the master definition of a single lab test including:
  - Reference ranges (gender-specific + universal fallback)
  - Critical limits for panic-value alerting
  - Expected result type (numeric, text, boolean)
  - Sample type required

تحتوي على التعريف الرئيسي للفحص المخبري بما في ذلك:
  - النطاقات المرجعية (حسب الجنس + القيمة الافتراضية العامة)
  - الحدود الحرجة لتنبيهات القيم الخطرة
  - نوع النتيجة المتوقعة (رقمية / نصية / ثنائية)
  - نوع العينة المطلوبة
"""

from odoo import api, fields, models

# ── Constant: result types ────────────────────────────────────────────────────
RESULT_TYPE_SELECTION = [
    ("numeric", "Numeric / رقمي"),
    ("text", "Text / نصي"),
    ("boolean", "Positive/Negative / إيجابي/سلبي"),
]

# ── Constant: sample types ────────────────────────────────────────────────────
SAMPLE_TYPE_SELECTION = [
    ("blood_venous", "Venous Blood / دم وريدي"),
    ("blood_capillary", "Capillary Blood / دم شعري"),
    ("urine", "Urine / بول"),
    ("stool", "Stool / براز"),
    ("sputum", "Sputum / بلغم"),
    ("swab", "Swab / مسحة"),
    ("csf", "CSF / سائل نخاعي"),
    ("other", "Other / أخرى"),
]


class LabTest(models.Model):
    _name = "lab.test"
    _description = "Lab Test / فحص مخبري"
    _inherit = ["mail.thread"]
    _order = "category_id, sequence, name"

    # ── Identity ─────────────────────────────────────────────────────────────
    name = fields.Char(
        string="Test Name",
        required=True,
        translate=True,
        tracking=True,
    )
    name_ar = fields.Char(
        string="Arabic Name / الاسم بالعربية",
        tracking=True,
    )
    code = fields.Char(
        string="Test Code / رمز الفحص",
        required=True,
        size=20,
        copy=False,
    )
    category_id = fields.Many2one(
        comodel_name="lab.test.category",
        string="Category / التصنيف",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    # ── Result type & sample ──────────────────────────────────────────────────
    result_type = fields.Selection(
        selection=RESULT_TYPE_SELECTION,
        string="Result Type / نوع النتيجة",
        required=True,
        default="numeric",
        tracking=True,
    )
    sample_type = fields.Selection(
        selection=SAMPLE_TYPE_SELECTION,
        string="Sample Type / نوع العينة",
        required=True,
        default="blood_venous",
        tracking=True,
    )
    result_uom = fields.Char(
        string="Unit / الوحدة",
        help="e.g. mg/dL, g/dL, 10³/µL",
    )
    turnaround_hours = fields.Float(
        string="Turnaround (hrs) / وقت الاستجابة (ساعة)",
        default=24.0,
        help="Expected time from sample receipt to result delivery",
    )
    description = fields.Text(
        string="Description / الوصف",
        translate=True,
    )
    instructions = fields.Text(
        string="Patient Instructions / تعليمات للمريض",
        translate=True,
        help="e.g. Fasting required / يشترط الصيام",
    )

    # ── Reference ranges — universal (fallback) ───────────────────────────────
    ref_low = fields.Float(
        string="Ref Low / الحد الأدنى المرجعي",
        digits=(10, 4),
    )
    ref_high = fields.Float(
        string="Ref High / الحد الأعلى المرجعي",
        digits=(10, 4),
    )

    # ── Reference ranges — gender-specific ───────────────────────────────────
    ref_low_male = fields.Float(
        string="Ref Low (Male) / الحد الأدنى (ذكر)",
        digits=(10, 4),
    )
    ref_high_male = fields.Float(
        string="Ref High (Male) / الحد الأعلى (ذكر)",
        digits=(10, 4),
    )
    ref_low_female = fields.Float(
        string="Ref Low (Female) / الحد الأدنى (أنثى)",
        digits=(10, 4),
    )
    ref_high_female = fields.Float(
        string="Ref High (Female) / الحد الأعلى (أنثى)",
        digits=(10, 4),
    )

    # ── Critical (panic) limits ───────────────────────────────────────────────
    critical_low = fields.Float(
        string="Critical Low / الحد الحرج الأدنى",
        digits=(10, 4),
        help="Below this value → critical_low flag / تحت هذه القيمة → تنبيه حرج أدنى",
    )
    critical_high = fields.Float(
        string="Critical High / الحد الحرج الأعلى",
        digits=(10, 4),
        help="Above this value → critical_high flag / فوق هذه القيمة → تنبيه حرج أعلى",
    )

    # ── Text / boolean result options ─────────────────────────────────────────
    normal_text_result = fields.Char(
        string="Normal Text Result / النتيجة النصية الطبيعية",
        help="For result_type=text, the 'normal' expected value",
    )

    # ── SQL constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        (
            "code_company_uniq",
            "UNIQUE(code, company_id)",
            "Test code must be unique per company / رمز الفحص يجب أن يكون فريداً.",
        )
    ]

    # ── Helpers ───────────────────────────────────────────────────────────────
    def get_reference_range(self, gender: str = "other") -> tuple:
        """Return (low, high) reference range for a given patient gender.

        Uses gender-specific ranges if available; falls back to universal.
        Returns (low, high) for the patient gender.

        يُرجع (الحد الأدنى، الحد الأعلى) للنطاق المرجعي حسب جنس المريض.
        يستخدم النطاق الخاص بالجنس إن وُجد، وإلا النطاق العام.
        """
        self.ensure_one()
        if gender == "male" and (self.ref_low_male or self.ref_high_male):
            return self.ref_low_male, self.ref_high_male
        if gender == "female" and (self.ref_low_female or self.ref_high_female):
            return self.ref_low_female, self.ref_high_female
        return self.ref_low, self.ref_high

    @api.depends("name", "name_ar", "code")
    def _compute_display_name(self) -> None:
        """Bilingual display name: code — EN / AR."""
        for rec in self:
            ar_part = f" / {rec.name_ar}" if rec.name_ar else ""
            rec.display_name = f"[{rec.code}] {rec.name}{ar_part}"
