# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
Health Specialty
التخصص الطبي

Medical specialty catalog.  Each specialty optionally links to a service
product used when invoicing a consultation (per OQ-02 decision: one product
per specialty).

كتالوج التخصصات الطبية. كل تخصص يرتبط اختيارياً بمنتج خدمة يُستخدم
عند فوترة الاستشارة (وفقاً لقرار OQ-02: منتج واحد لكل تخصص).
"""
from __future__ import annotations

from odoo import api, fields, models


class HealthSpecialty(models.Model):
    """Medical specialty with linked consultation product.

    التخصص الطبي مع منتج الاستشارة المرتبط.
    """

    _name = 'health.specialty'
    _description = 'Medical Specialty / التخصص الطبي'
    _order = 'name'
    _rec_name = 'name'

    # ── Identity ──────────────────────────────────────────────────────────
    name: fields.Char = fields.Char(
        string='Specialty / التخصص',
        required=True,
        translate=True,
        index=True,
        tracking=True,
    )
    code: fields.Char = fields.Char(
        string='Code / الرمز',
        required=True,
        size=20,
        index=True,
        tracking=True,
    )

    # ── Ownership ─────────────────────────────────────────────────────────
    company_id: fields.Many2one = fields.Many2one(
        comodel_name='res.company',
        string='Company / الشركة',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        tracking=True,
    )

    # ── Financial integration (OQ-02: per-specialty consultation product) ─
    consultation_product_id: fields.Many2one = fields.Many2one(
        comodel_name='product.product',
        string='Consultation Product / منتج الاستشارة',
        domain="[('type', '=', 'service')]",
        ondelete='set null',
        help=(
            'Service product used when invoicing a consultation of this '
            'specialty.  Must be of type "Service".\n'
            'المنتج الخدمي المستخدم عند فوترة الاستشارة لهذا التخصص. '
            'يجب أن يكون من نوع "خدمة".'
        ),
    )

    # ── UI helpers ────────────────────────────────────────────────────────
    color: fields.Integer = fields.Integer(
        string='Color Index / اللون',
        default=0,
    )
    active: fields.Boolean = fields.Boolean(
        string='Active / نشط',
        default=True,
        tracking=True,
    )

    # ── Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'code_company_unique',
            'UNIQUE(code, company_id)',
            'Specialty code must be unique per company. '
            '/ رمز التخصص يجب أن يكون فريداً لكل شركة.',
        ),
    ]

    @api.onchange('name')
    def _onchange_name_suggest_code(self) -> None:
        """Auto-suggest a code from the specialty name initials.

        اقتراح تلقائي للرمز من أحرف اسم التخصص.
        """
        if self.name and not self.code:
            words = self.name.upper().split()
            self.code = ''.join(w[0] for w in words if w)[:10]
