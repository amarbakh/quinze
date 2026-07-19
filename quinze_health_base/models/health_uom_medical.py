# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
Medical Units of Measure
وحدات القياس الطبية

A lightweight model for medical-specific units (mg, mL, IU, tablet, vial,
drop, etc.) separate from Odoo's stock UoM so that pharmaceutical dosing
does not pollute the inventory UoM categories.

نموذج خفيف لوحدات القياس الطبية المخصصة (ملغ، مل، وحدة دولية، حبة،
أمبولة، قطرة، إلخ) منفصل عن وحدات القياس الخاصة بالمخزون.
"""
from __future__ import annotations

from odoo import fields, models


class HealthUomMedical(models.Model):
    """Medical unit of measure for dosage and lab reference ranges.

    وحدة قياس طبية للجرعات ونطاقات المراجع المخبرية.
    """

    _name = 'health.uom.medical'
    _description = 'Medical Unit of Measure / وحدة قياس طبية'
    _order = 'uom_type, name'

    UOM_TYPE = [
        ('mass',          'Mass / الكتلة'),
        ('volume',        'Volume / الحجم'),
        ('count',         'Count / العدد'),
        ('concentration', 'Concentration / التركيز'),
        ('activity',      'Activity / النشاط البيولوجي'),
        ('ratio',         'Ratio / النسبة'),
        ('other',         'Other / أخرى'),
    ]

    # ── Fields ───────────────────────────────────────────────────────────
    name: fields.Char = fields.Char(
        string='Unit Name / اسم الوحدة',
        required=True,
        translate=True,
        index=True,
    )
    symbol: fields.Char = fields.Char(
        string='Symbol / الرمز',
        required=True,
        size=20,
        help=(
            'Abbreviated symbol printed on reports and prescriptions '
            '(e.g. mg, mL, IU).\n'
            'الرمز المختصر المطبوع في التقارير والوصفات (مثل: ملغ، مل، IU).'
        ),
    )
    uom_type: fields.Selection = fields.Selection(
        selection=UOM_TYPE,
        string='Type / النوع',
        required=True,
        default='count',
        index=True,
    )
    active: fields.Boolean = fields.Boolean(
        string='Active / نشط',
        default=True,
    )

    # ── Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'symbol_unique',
            'UNIQUE(symbol)',
            'Symbol must be unique. / الرمز يجب أن يكون فريداً.',
        ),
    ]

    def name_get(self) -> list[tuple[int, str]]:
        """Return 'Name (symbol)' for display.

        إرجاع 'الاسم (الرمز)' للعرض.
        """
        return [(r.id, f'{r.name} ({r.symbol})') for r in self]
