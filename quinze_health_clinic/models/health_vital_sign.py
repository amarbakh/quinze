# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
"""
Health Vital Sign
العلامات الحيوية

One-to-many child of health.encounter.
Stores a single set of vital readings taken at one point in time.
BMI is computed automatically from weight and height.

أحد مع كثيرين من الزيارة الطبية.
يخزن مجموعة قراءات حيوية واحدة مأخوذة في وقت معين.
مؤشر كتلة الجسم يُحسب تلقائياً من الوزن والطول.
"""
from __future__ import annotations

from odoo import api, fields, models


class HealthVitalSign(models.Model):
    """Vital sign readings attached to an encounter.

    قراءات العلامات الحيوية المرتبطة بزيارة طبية.
    """

    _name = 'health.vital.sign'
    _description = 'Vital Signs / العلامات الحيوية'
    _order = 'measured_at desc'

    # ── Parent ────────────────────────────────────────────────────────────
    encounter_id: fields.Many2one = fields.Many2one(
        comodel_name='health.encounter',
        string='Encounter / الزيارة',
        required=True,
        index=True,
        ondelete='cascade',
    )
    company_id: fields.Many2one = fields.Many2one(
        related='encounter_id.company_id',
        store=True,
        index=True,
    )

    # ── Timestamp ─────────────────────────────────────────────────────────
    measured_at: fields.Datetime = fields.Datetime(
        string='Measured At / وقت القياس',
        required=True,
        default=fields.Datetime.now,
    )
    measured_by: fields.Many2one = fields.Many2one(
        comodel_name='res.users',
        string='Measured By / قِيس بواسطة',
        default=lambda self: self.env.user,
        ondelete='set null',
    )

    # ── Cardiovascular ────────────────────────────────────────────────────
    systolic_bp: fields.Float = fields.Float(
        string='Systolic BP (mmHg) / ضغط الدم الانقباضي',
        digits=(5, 1),
        help='Normal range: 90–120 mmHg',
    )
    diastolic_bp: fields.Float = fields.Float(
        string='Diastolic BP (mmHg) / ضغط الدم الانبساطي',
        digits=(5, 1),
        help='Normal range: 60–80 mmHg',
    )
    heart_rate: fields.Float = fields.Float(
        string='Heart Rate (bpm) / معدل النبض',
        digits=(5, 1),
        help='Normal adult range: 60–100 bpm',
    )

    # ── Respiratory ───────────────────────────────────────────────────────
    respiratory_rate: fields.Float = fields.Float(
        string='Respiratory Rate (br/min) / معدل التنفس',
        digits=(5, 1),
    )
    spo2: fields.Float = fields.Float(
        string='SpO₂ (%) / تشبع الأكسجين',
        digits=(5, 1),
        help='Normal: ≥95%',
    )

    # ── Temperature ───────────────────────────────────────────────────────
    temperature: fields.Float = fields.Float(
        string='Temperature (°C) / درجة الحرارة',
        digits=(5, 2),
        help='Normal: 36.1–37.2 °C',
    )

    # ── Anthropometric ────────────────────────────────────────────────────
    weight_kg: fields.Float = fields.Float(
        string='Weight (kg) / الوزن',
        digits=(6, 2),
    )
    height_cm: fields.Float = fields.Float(
        string='Height (cm) / الطول',
        digits=(5, 1),
    )
    bmi: fields.Float = fields.Float(
        string='BMI / مؤشر كتلة الجسم',
        compute='_compute_bmi',
        store=True,
        digits=(5, 2),
    )
    bmi_category: fields.Char = fields.Char(
        string='BMI Category / تصنيف مؤشر كتلة الجسم',
        compute='_compute_bmi',
        store=True,
    )

    # ── Glucose ───────────────────────────────────────────────────────────
    blood_glucose: fields.Float = fields.Float(
        string='Blood Glucose (mg/dL) / سكر الدم',
        digits=(6, 1),
    )

    # ── Notes ─────────────────────────────────────────────────────────────
    note: fields.Text = fields.Text(
        string='Notes / ملاحظات',
    )

    # ── Computed ──────────────────────────────────────────────────────────

    @api.depends('weight_kg', 'height_cm')
    def _compute_bmi(self) -> None:
        """Compute BMI and category from weight and height.

        حساب مؤشر كتلة الجسم وتصنيفه من الوزن والطول.
        """
        for rec in self:
            if rec.height_cm and rec.weight_kg and rec.height_cm > 0:
                h_m = rec.height_cm / 100.0
                bmi = rec.weight_kg / (h_m ** 2)
                rec.bmi = round(bmi, 2)
                if bmi < 18.5:
                    rec.bmi_category = 'Underweight / نقص الوزن'
                elif bmi < 25.0:
                    rec.bmi_category = 'Normal / طبيعي'
                elif bmi < 30.0:
                    rec.bmi_category = 'Overweight / زيادة الوزن'
                else:
                    rec.bmi_category = 'Obese / سمنة'
            else:
                rec.bmi = 0.0
                rec.bmi_category = ''
