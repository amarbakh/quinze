# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
"""
Health Prescription Line
سطر الوصفة الطبية

One line per medication in a prescription.
Contains drug, dose, frequency, duration, and route.

سطر واحد لكل دواء في الوصفة الطبية.
يحتوي على الدواء والجرعة والتكرار والمدة والطريق.
"""
from __future__ import annotations

from odoo import api, fields, models


class HealthPrescriptionLine(models.Model):
    """A single drug line within a prescription.

    سطر دواء واحد داخل الوصفة الطبية.
    """

    _name = 'health.prescription.line'
    _description = 'Prescription Line / سطر وصفة طبية'
    _order = 'sequence, id'

    ROUTE_SELECTION = [
        ('oral',       'Oral / فموي'),
        ('iv',         'Intravenous (IV) / وريدي'),
        ('im',         'Intramuscular (IM) / عضلي'),
        ('sc',         'Subcutaneous (SC) / تحت الجلد'),
        ('sl',         'Sublingual / تحت اللسان'),
        ('topical',    'Topical / موضعي'),
        ('inhaled',    'Inhaled / استنشاق'),
        ('ophthalmic', 'Ophthalmic / عيني'),
        ('otic',       'Otic / أذني'),
        ('rectal',     'Rectal / شرجي'),
        ('nasal',      'Nasal / أنفي'),
        ('other',      'Other / أخرى'),
    ]

    FREQUENCY_SELECTION = [
        ('once',    'Once / مرة واحدة'),
        ('od',      'Once Daily (OD) / مرة يومياً'),
        ('bd',      'Twice Daily (BD) / مرتان يومياً'),
        ('tds',     'Three Times Daily (TDS) / ثلاث مرات يومياً'),
        ('qid',     'Four Times Daily (QID) / أربع مرات يومياً'),
        ('prn',     'As Needed (PRN) / عند الحاجة'),
        ('stat',    'Immediately (STAT) / فوراً'),
        ('weekly',  'Once Weekly / مرة أسبوعياً'),
        ('other',   'Other / أخرى'),
    ]

    # ── Parent ────────────────────────────────────────────────────────────
    prescription_id: fields.Many2one = fields.Many2one(
        comodel_name='health.prescription',
        string='Prescription / الوصفة',
        required=True,
        index=True,
        ondelete='cascade',
    )
    sequence: fields.Integer = fields.Integer(
        string='Sequence',
        default=10,
    )

    # ── Drug ──────────────────────────────────────────────────────────────
    product_id: fields.Many2one = fields.Many2one(
        comodel_name='product.product',
        string='Medication / الدواء',
        required=True,
        index=True,
        domain="[('is_medication', '=', True)]",
        ondelete='restrict',
        help=(
            'Must be a medication product (is_medication=True). '
            'Set in the Pharmacy module.\n'
            'يجب أن يكون منتجاً دوائياً (is_medication=True). '
            'يُضبط في وحدة الصيدلية.'
        ),
    )
    drug_name_display: fields.Char = fields.Char(
        string='Drug Name (Override) / اسم الدواء (تجاوز)',
        help=(
            'Optional: override the product name on the printed prescription.\n'
            'اختياري: تجاوز اسم المنتج على الوصفة المطبوعة.'
        ),
    )
    drug_name_ar: fields.Char = fields.Char(
        string='Drug Name (AR) / اسم الدواء (عربي)',
        help='Arabic name to print on prescription.\n'
             'الاسم العربي للطباعة على الوصفة.',
    )

    # ── Dosage ────────────────────────────────────────────────────────────
    dose: fields.Float = fields.Float(
        string='Dose / الجرعة',
        digits=(8, 2),
    )
    dose_uom_id: fields.Many2one = fields.Many2one(
        comodel_name='health.uom.medical',
        string='Unit / الوحدة',
        ondelete='restrict',
    )
    frequency: fields.Selection = fields.Selection(
        selection=FREQUENCY_SELECTION,
        string='Frequency / التكرار',
        default='od',
    )
    frequency_note: fields.Char = fields.Char(
        string='Frequency Note / ملاحظة التكرار',
        help='Used when frequency=other.',
    )
    duration_days: fields.Integer = fields.Integer(
        string='Duration (days) / المدة (أيام)',
    )
    route: fields.Selection = fields.Selection(
        selection=ROUTE_SELECTION,
        string='Route / طريق الإعطاء',
        default='oral',
    )

    # ── Dispensing tracking (updated by pharmacy module) ─────────────────
    qty_to_dispense: fields.Float = fields.Float(
        string='Qty to Dispense / الكمية للصرف',
        digits=(8, 2),
        compute='_compute_qty_to_dispense',
        store=True,
        help='Total quantity = dose × (frequency_per_day × duration_days).',
    )
    qty_dispensed: fields.Float = fields.Float(
        string='Qty Dispensed / الكمية المصروفة',
        digits=(8, 2),
        default=0.0,
        readonly=True,
        help='Updated by the pharmacy dispensing module.',
    )

    # ── Instructions ──────────────────────────────────────────────────────
    instructions: fields.Text = fields.Text(
        string='Instructions / التعليمات',
        help=(
            'Patient-facing instructions (printed on prescription).\n'
            'تعليمات للمريض (مطبوعة على الوصفة).'
        ),
    )

    # ── Computed ──────────────────────────────────────────────────────────

    @api.depends('dose', 'frequency', 'duration_days')
    def _compute_qty_to_dispense(self) -> None:
        """Estimate total quantity needed for the full course.

        تقدير الكمية الإجمالية اللازمة للدورة الكاملة.
        """
        DAILY_DOSES = {
            'once': 1, 'od': 1, 'bd': 2, 'tds': 3, 'qid': 4,
            'prn': 1, 'stat': 1, 'weekly': 1 / 7, 'other': 1,
        }
        for rec in self:
            if rec.dose and rec.duration_days and rec.frequency:
                daily = DAILY_DOSES.get(rec.frequency, 1)
                rec.qty_to_dispense = rec.dose * daily * rec.duration_days
            else:
                rec.qty_to_dispense = rec.dose or 0.0

    @api.onchange('product_id')
    def _onchange_product_id(self) -> None:
        """Pre-fill Arabic drug name and route from product attributes.

        ملء اسم الدواء العربي وطريق الإعطاء من خصائص المنتج.
        """
        if self.product_id:
            tmpl = self.product_id.product_tmpl_id
            # generic_name_ar is added by quinze_health_pharmacy; safe to check
            if hasattr(tmpl, 'generic_name_ar') and tmpl.generic_name_ar:
                self.drug_name_ar = tmpl.generic_name_ar
