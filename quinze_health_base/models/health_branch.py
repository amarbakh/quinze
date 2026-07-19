# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
Health Branch
فرع المنشأة الصحية

Represents a physical branch (location) of a multi-branch medical center
operating under a single Odoo company.  When multiple Odoo companies are
used, each company manages its own branches independently.

يمثل الفرع المادي لمركز طبي متعدد الفروع يعمل ضمن شركة أودو واحدة.
"""
from __future__ import annotations

from odoo import fields, models


class HealthBranch(models.Model):
    """Physical branch of a medical center.

    فرع مادي للمركز الصحي.
    """

    _name = 'health.branch'
    _description = 'Health Branch / فرع صحي'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'company_id, code'
    _rec_name = 'name'

    # ── Identity ──────────────────────────────────────────────────────────
    name: fields.Char = fields.Char(
        string='Branch Name / اسم الفرع',
        required=True,
        translate=True,
        index=True,
        tracking=True,
    )
    code: fields.Char = fields.Char(
        string='Code / الرمز',
        required=True,
        size=10,
        index=True,
        tracking=True,
        help=(
            'Short alphanumeric code used in document numbers (e.g. RYD, JED).\n'
            'رمز قصير يُستخدم في أرقام المستندات (مثل: RYD, JED).'
        ),
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

    # ── Address ───────────────────────────────────────────────────────────
    partner_id: fields.Many2one = fields.Many2one(
        comodel_name='res.partner',
        string='Address / العنوان',
        domain="[('type', 'in', ['delivery', 'other', 'contact'])]",
        help=(
            'Partner record holding the physical address of this branch.\n'
            'سجل الشريك الذي يحتوي على العنوان المادي لهذا الفرع.'
        ),
    )

    # ── Status ────────────────────────────────────────────────────────────
    active: fields.Boolean = fields.Boolean(
        string='Active / نشط',
        default=True,
        tracking=True,
    )
    note: fields.Text = fields.Text(
        string='Notes / ملاحظات',
    )

    # ── Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'code_company_unique',
            'UNIQUE(code, company_id)',
            'Branch code must be unique per company. '
            '/ رمز الفرع يجب أن يكون فريداً لكل شركة.',
        ),
    ]

    def name_get(self) -> list[tuple[int, str]]:
        """Return 'CODE — Name' for dropdown display.

        إرجاع 'الرمز — الاسم' لعرض القائمة المنسدلة.
        """
        return [(rec.id, f'{rec.code} — {rec.name}') for rec in self]
