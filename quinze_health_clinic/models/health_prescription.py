# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
"""
Health Prescription
الوصفة الطبية

Header model for a prescription.  One prescription per encounter visit,
though a patient may have multiple over time.

State machine:
  draft → confirmed → [partially_dispensed] → dispensed
        ↘ cancelled

The dispensing module (Phase 4) updates state from confirmed →
partially_dispensed / dispensed.

نموذج رأس الوصفة الطبية.
"""
from __future__ import annotations

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class HealthPrescription(models.Model):
    """Prescription header.

    رأس الوصفة الطبية.
    """

    _name = 'health.prescription'
    _description = 'Prescription / وصفة طبية'
    _inherit = ['health.mixin']
    _order = 'prescription_date desc, prescription_number desc'
    _rec_name = 'prescription_number'

    STATE_SELECTION = [
        ('draft',               'Draft / مسودة'),
        ('confirmed',           'Confirmed / مؤكدة'),
        ('partially_dispensed', 'Partially Dispensed / صرف جزئي'),
        ('dispensed',           'Dispensed / مصروفة'),
        ('cancelled',           'Cancelled / ملغاة'),
    ]

    # ── Identity ──────────────────────────────────────────────────────────
    prescription_number: fields.Char = fields.Char(
        string='Prescription No. / رقم الوصفة',
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
        index=True,
        ondelete='restrict',
    )
    patient_id: fields.Many2one = fields.Many2one(
        comodel_name='health.patient',
        string='Patient / المريض',
        required=True,
        index=True,
        ondelete='restrict',
        tracking=True,
    )
    doctor_id: fields.Many2one = fields.Many2one(
        comodel_name='res.partner',
        string='Doctor / الطبيب',
        required=True,
        index=True,
        domain="[('is_doctor', '=', True)]",
        ondelete='restrict',
        tracking=True,
    )

    # ── Dates ─────────────────────────────────────────────────────────────
    prescription_date: fields.Date = fields.Date(
        string='Date / التاريخ',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    valid_until: fields.Date = fields.Date(
        string='Valid Until / صالحة حتى',
        default=lambda self: fields.Date.today() + timedelta(days=30),
        tracking=True,
        help=(
            'Prescription expiry date. '
            'Pharmacy cannot dispense after this date.\n'
            'تاريخ انتهاء صلاحية الوصفة. '
            'لا يمكن للصيدلية الصرف بعد هذا التاريخ.'
        ),
    )
    is_expired: fields.Boolean = fields.Boolean(
        string='Expired / منتهية الصلاحية',
        compute='_compute_is_expired',
        store=True,
    )

    # ── Lines ─────────────────────────────────────────────────────────────
    prescription_line_ids: fields.One2many = fields.One2many(
        comodel_name='health.prescription.line',
        inverse_name='prescription_id',
        string='Medications / الأدوية',
    )
    line_count: fields.Integer = fields.Integer(
        string='Drug Count',
        compute='_compute_line_count',
    )

    # ── Diagnosis link ────────────────────────────────────────────────────
    diagnosis_ids: fields.Many2many = fields.Many2many(
        related='encounter_id.diagnosis_ids',
        string='Diagnoses / التشخيصات',
        readonly=True,
    )

    # ── Onchange ──────────────────────────────────────────────────────────

    @api.onchange('prescription_date')
    def _onchange_prescription_date(self) -> None:
        """Keep the validity window aligned with the issue date.

        مواءمة تاريخ انتهاء الصلاحية مع تاريخ الإصدار.
        """
        if self.prescription_date:
            self.valid_until = self.prescription_date + timedelta(days=30)

    # ── Computed ──────────────────────────────────────────────────────────

    @api.depends('valid_until')
    def _compute_is_expired(self) -> None:
        today = fields.Date.today()
        for rec in self:
            rec.is_expired = bool(rec.valid_until and rec.valid_until < today)

    def _compute_line_count(self) -> None:
        for rec in self:
            rec.line_count = len(rec.prescription_line_ids)

    # ── ORM hooks ─────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> 'HealthPrescription':
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('prescription_number', 'New') == 'New':
                vals['prescription_number'] = seq.next_by_code(
                    'health.prescription'
                ) or 'New'
        return super().create(vals_list)

    @api.onchange('encounter_id')
    def _onchange_encounter_id(self) -> None:
        """Auto-fill patient and doctor from encounter.

        ملء المريض والطبيب تلقائياً من الزيارة.
        """
        if self.encounter_id:
            self.patient_id = self.encounter_id.patient_id
            self.doctor_id = self.encounter_id.doctor_id

    # ── State transitions ─────────────────────────────────────────────────

    def action_confirm(self) -> None:
        """Doctor signs and confirms prescription: draft → confirmed.

        الطبيب يوقّع ويؤكد الوصفة: مسودة → مؤكدة.
        """
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    'Only draft prescriptions can be confirmed.\n'
                    'يمكن تأكيد الوصفات في المسودة فقط.'
                )
            if not rec.prescription_line_ids:
                raise UserError(
                    'At least one medication line is required.\n'
                    'مطلوب سطر دواء واحد على الأقل.'
                )
            rec.write({'state': 'confirmed'})

    def action_cancel(self) -> None:
        """Cancel prescription.

        إلغاء الوصفة.
        """
        for rec in self:
            if rec.state == 'dispensed':
                raise UserError(
                    'Fully dispensed prescriptions cannot be cancelled.\n'
                    'لا يمكن إلغاء الوصفات المصروفة بالكامل.'
                )
            rec.write({'state': 'cancelled'})

    def action_reset_draft(self) -> None:
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(
                    'Only cancelled prescriptions can be reset to draft.\n'
                    'يمكن إعادة تعيين الوصفات الملغاة فقط.'
                )
            rec.write({'state': 'draft'})

    # ── Report ────────────────────────────────────────────────────────────

    def action_print_prescription(self) -> dict:
        """Print bilingual prescription PDF.

        طباعة الوصفة الطبية ثنائية اللغة.
        """
        return self.env.ref(
            'quinze_health_clinic.action_report_health_prescription'
        ).report_action(self)
