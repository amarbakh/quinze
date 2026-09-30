# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
"""
Health Lab Request — Bridge from Clinic to Lab
طلب المختبر — الجسر من العيادة إلى المختبر

When quinze_health_lab is installed, it extends this model to add:
  - lab_test_ids (m2m to lab.test)
  - lab_order_id (m2m to lab.order)
  - _action_create_lab_order() override

In Phase 2 (clinic standalone) this model carries the request number,
state, and a free-text notes field for test descriptions.

عند تثبيت quinze_health_lab يتم تمديد هذا النموذج لإضافة:
  - lab_test_ids (علاقة m2m مع lab.test)
  - lab_order_id (FK إلى lab.order)
"""
from __future__ import annotations

from odoo import api, fields, models
from odoo.exceptions import UserError


class HealthLabRequest(models.Model):
    """Lab work request raised by a doctor from an encounter.

    طلب عمل مخبري يرفعه الطبيب من زيارة طبية.
    """

    _name = 'health.lab.request'
    _description = 'Lab Request / طلب مختبر'
    _inherit = ['health.mixin']
    _order = 'request_date desc, request_number desc'
    _rec_name = 'request_number'

    STATE_SELECTION = [
        ('draft',     'Draft / مسودة'),
        ('confirmed', 'Confirmed / مؤكد'),
        ('sent',      'Sent to Lab / أُرسل للمختبر'),
        ('done',      'Done / منتهٍ'),
        ('cancelled', 'Cancelled / ملغى'),
    ]

    # ── Identity ──────────────────────────────────────────────────────────
    request_number: fields.Char = fields.Char(
        string='Request No. / رقم الطلب',
        readonly=True,
        copy=False,
        index=True,
        default='New',
        tracking=True,
    )
    state: fields.Selection = fields.Selection(
        selection=STATE_SELECTION,
        string='Status / الحالة',
        default='draft',
        required=True,
        index=True,
        tracking=True,
    )

    # ── Participants ──────────────────────────────────────────────────────
    encounter_id: fields.Many2one = fields.Many2one(
        comodel_name='health.encounter',
        string='Encounter / الزيارة',
        required=True,
        index=True,
        ondelete='restrict',
        tracking=True,
    )
    patient_id: fields.Many2one = fields.Many2one(
        comodel_name='health.patient',
        related='encounter_id.patient_id',
        string='Patient / المريض',
        store=True,
        readonly=True,
        index=True,
    )
    doctor_id: fields.Many2one = fields.Many2one(
        comodel_name='res.partner',
        related='encounter_id.doctor_id',
        string='Doctor / الطبيب',
        store=True,
        readonly=True,
    )
    request_date: fields.Date = fields.Date(
        string='Date / التاريخ',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )

    # ── Tests requested (free-text in Phase 2; extended by lab module) ────
    tests_description: fields.Text = fields.Text(
        string='Tests Requested / الفحوصات المطلوبة',
        help=(
            'Free-text description of tests when the lab module is not '
            'installed.  Once quinze_health_lab is installed, use the '
            'lab_test_ids field instead.\n'
            'وصف نصي للفحوصات عند غياب وحدة المختبر. '
            'بعد تثبيت quinze_health_lab استخدم حقل lab_test_ids.'
        ),
    )
    priority: fields.Selection = fields.Selection(
        selection=[
            ('normal', 'Normal / عادي'),
            ('urgent', 'Urgent / عاجل'),
            ('stat',   'STAT / فوري'),
        ],
        string='Priority / الأولوية',
        default='normal',
        tracking=True,
    )
    clinical_indication: fields.Text = fields.Text(
        string='Clinical Indication / المبرر السريري',
    )

    # ── ORM hooks ─────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> 'HealthLabRequest':
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('request_number', 'New') == 'New':
                vals['request_number'] = seq.next_by_code(
                    'health.lab.request'
                ) or 'New'
        return super().create(vals_list)

    # ── State transitions ─────────────────────────────────────────────────

    def action_confirm(self) -> None:
        """Confirm lab request and (if lab module installed) create lab order.

        تأكيد طلب المختبر وإنشاء أمر المختبر (إذا كانت الوحدة مثبتة).
        """
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    'Only draft lab requests can be confirmed.\n'
                    'يمكن تأكيد الطلبات في المسودة فقط.'
                )
            rec.write({'state': 'confirmed'})
            # Hook: extended by quinze_health_lab to create lab.order
            rec._action_create_lab_order()

    def _action_create_lab_order(self) -> None:
        """Hook called on confirmation.  Override in lab module.

        ربط يُستدعى عند التأكيد. يُتجاوز في وحدة المختبر.
        """
        # Base implementation: no-op (lab module not installed)
        pass

    def action_cancel(self) -> None:
        """Cancel lab request.

        إلغاء طلب المختبر.
        """
        for rec in self:
            if rec.state == 'done':
                raise UserError(
                    'Completed lab requests cannot be cancelled.\n'
                    'لا يمكن إلغاء الطلبات المنتهية.'
                )
            rec.write({'state': 'cancelled'})

    def action_reset_draft(self) -> None:
        """Reset cancelled lab request back to draft.

        إعادة الطلب الملغى إلى المسودة.
        """
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(
                    'Only cancelled requests can be reset to draft.\n'
                    'يمكن إعادة الطلبات الملغاة فقط إلى المسودة.'
                )
            rec.write({'state': 'draft'})

