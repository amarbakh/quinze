# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
Health Allergy
الحساسية الطبية

Shared allergy catalog referenced from res.partner (patient allergies) and
from health.prescription.line (contraindication checking).

كتالوج الحساسية الطبية المشترك، يُستخدم من سجل الشريك (حساسيات المريض)
ومن سطر الوصفة الطبية (فحص موانع الاستعمال).
"""
from __future__ import annotations

from odoo import fields, models


class HealthAllergy(models.Model):
    """Allergy catalog entry.

    إدخال في كتالوج الحساسية.
    """

    _name = 'health.allergy'
    _description = 'Health Allergy / حساسية طبية'
    _order = 'allergy_type, name'

    # ── Allergy type selection ────────────────────────────────────────────
    ALLERGY_TYPE = [
        ('drug',         'Drug / دواء'),
        ('food',         'Food / غذاء'),
        ('environmental','Environmental / بيئي'),
        ('latex',        'Latex / لاتكس'),
        ('contrast',     'Contrast Media / وسيط تباين'),
        ('other',        'Other / أخرى'),
    ]

    # ── Fields ───────────────────────────────────────────────────────────
    name: fields.Char = fields.Char(
        string='Allergy / اسم الحساسية',
        required=True,
        translate=True,
        index=True,
    )
    allergy_type: fields.Selection = fields.Selection(
        selection=ALLERGY_TYPE,
        string='Type / النوع',
        required=True,
        default='drug',
        index=True,
    )
    active: fields.Boolean = fields.Boolean(
        string='Active / نشط',
        default=True,
    )
    note: fields.Text = fields.Text(
        string='Clinical Notes / ملاحظات سريرية',
        translate=True,
        help=(
            'Cross-reactivity notes, alternative recommendations, etc.\n'
            'ملاحظات التفاعل المتقاطع، البدائل الموصى بها، إلخ.'
        ),
    )

    # ── Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'name_type_unique',
            'UNIQUE(name, allergy_type)',
            'Allergy name must be unique within its type. '
            '/ اسم الحساسية يجب أن يكون فريداً ضمن نوعه.',
        ),
    ]
