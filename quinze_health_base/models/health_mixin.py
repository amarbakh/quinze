# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
Health Abstract Mixin
نموذج مجرد مشترك للنظام الصحي

Provides common infrastructure fields that every QUINZE Health transactional
model inherits.  Downstream modules do ``_inherit = ['health.mixin']`` and
get company_id, active, note, branch_id, mail.thread, and mail.activity
support for free.

يوفر الحقول البنيوية المشتركة لجميع نماذج نظام QUINZE الصحي المعاملاتية.
"""
from __future__ import annotations

import sys

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# ---------------------------------------------------------------------------
# Enterprise feature flag (safe — never raises ImportError)
# ---------------------------------------------------------------------------
_ENTERPRISE = 'web_enterprise' in sys.modules


class HealthMixin(models.AbstractModel):
    """Abstract mixin: company, branch, active, note + mail threads.

    نموذج مجرد: الشركة، الفرع، النشاط، الملاحظة + سجلات البريد.

    Usage / الاستخدام::

        class MyModel(models.Model):
            _name = 'my.model'
            _inherit = ['health.mixin']
            ...
    """

    _name = 'health.mixin'
    _description = 'Health Abstract Mixin / النموذج المجرد الصحي'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ── Company (mandatory, multi-company aware) ──────────────────────────
    company_id: fields.Many2one = fields.Many2one(
        comodel_name='res.company',
        string='Company / الشركة',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        tracking=True,
        help=(
            'The company this record belongs to.\n'
            'الشركة التي ينتمي إليها هذا السجل.'
        ),
    )

    # ── Branch (optional — used when single company has multiple locations) ─
    branch_id: fields.Many2one = fields.Many2one(
        comodel_name='health.branch',
        string='Branch / الفرع',
        index=True,
        ondelete='restrict',
        domain="[('active', '=', True)]",
        tracking=True,
        help=(
            'Physical branch of the medical center.\n'
            'الفرع المادي للمركز الصحي.'
        ),
    )

    # ── Soft-delete ───────────────────────────────────────────────────────
    active: fields.Boolean = fields.Boolean(
        string='Active / نشط',
        default=True,
        tracking=True,
        help=(
            'Uncheck to archive this record without permanent deletion.\n'
            'أزل التحديد لأرشفة هذا السجل دون حذف دائم.'
        ),
    )

    # ── Internal notes ────────────────────────────────────────────────────
    note: fields.Html = fields.Html(
        string='Internal Notes / ملاحظات داخلية',
        sanitize=True,
        sanitize_tags=True,
    )

    # ── Helpers ───────────────────────────────────────────────────────────
    @api.model
    def _is_enterprise(self) -> bool:
        """Return True if Odoo Enterprise web module is loaded.

        إرجاع True إذا كانت وحدة Enterprise محملة.
        """
        return _ENTERPRISE

    @api.constrains('company_id', 'branch_id')
    def _check_branch_company(self) -> None:
        """Ensure branch belongs to the record's company.

        التحقق من أن الفرع ينتمي لشركة السجل.
        """
        for rec in self:
            if rec.branch_id and rec.branch_id.company_id != rec.company_id:
                raise ValidationError(
                    'The selected branch does not belong to the record\'s company.\n'
                    'الفرع المحدد لا ينتمي لشركة السجل.'
                )
