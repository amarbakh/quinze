# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
"""
Health Encounter — The Clinical Visit
الزيارة السريرية

State machine:
  draft → in_progress → done → invoiced
       ↘ cancelled ↗

Transition to ``invoiced`` posts an account.move (out_invoice) using
the doctor's specialty consultation product (per OQ-02).

آلة الحالات: مسودة → جارٍ → منتهٍ → مفوتر
"""
from __future__ import annotations

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class HealthEncounter(models.Model):
    """Clinical encounter — the actual visit record.

    الزيارة السريرية — سجل الزيارة الفعلية.
    """

    _name = 'health.encounter'
    _description = 'Health Encounter / زيارة طبية'
    _inherit = ['health.mixin']
    _order = 'encounter_date desc, encounter_number desc'
    _rec_name = 'encounter_number'

    STATE_SELECTION = [
        ('draft',       'Draft / مسودة'),
        ('in_progress', 'In Progress / جارٍ'),
        ('done',        'Done / منتهٍ'),
        ('invoiced',    'Invoiced / مفوتر'),
        ('cancelled',   'Cancelled / ملغى'),
    ]

    # ── Identity ──────────────────────────────────────────────────────────
    encounter_number: fields.Char = fields.Char(
        string='Encounter No. / رقم الزيارة',
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
    appointment_id: fields.Many2one = fields.Many2one(
        comodel_name='health.appointment',
        string='Appointment / الموعد',
        index=True,
        ondelete='set null',
        copy=False,
    )
    encounter_date: fields.Date = fields.Date(
        string='Date / التاريخ',
        required=True,
        default=fields.Date.today,
        index=True,
        tracking=True,
    )

    # ── Clinical data ─────────────────────────────────────────────────────
    chief_complaint: fields.Text = fields.Text(
        string='Chief Complaint / الشكوى الرئيسية',
        tracking=True,
    )
    clinical_notes: fields.Html = fields.Html(
        string='Clinical Notes / الملاحظات السريرية',
        sanitize=True,
    )
    diagnosis_ids: fields.Many2many = fields.Many2many(
        comodel_name='health.icd10',
        relation='encounter_icd10_rel',
        column1='encounter_id',
        column2='icd10_id',
        string='Diagnoses / التشخيصات',
        tracking=True,
    )

    # ── One2many children ─────────────────────────────────────────────────
    vital_sign_ids: fields.One2many = fields.One2many(
        comodel_name='health.vital.sign',
        inverse_name='encounter_id',
        string='Vital Signs / العلامات الحيوية',
    )
    prescription_ids: fields.One2many = fields.One2many(
        comodel_name='health.prescription',
        inverse_name='encounter_id',
        string='Prescriptions / الوصفات الطبية',
    )
    lab_request_ids: fields.One2many = fields.One2many(
        comodel_name='health.lab.request',
        inverse_name='encounter_id',
        string='Lab Requests / طلبات المختبر',
    )

    # ── Financial ─────────────────────────────────────────────────────────
    invoice_id: fields.Many2one = fields.Many2one(
        comodel_name='account.move',
        string='Invoice / الفاتورة',
        readonly=True,
        copy=False,
        ondelete='set null',
        tracking=True,
    )
    invoice_state: fields.Selection = fields.Selection(
        selection=[
            ('not_paid', 'Not Paid'),
            ('in_payment', 'In Payment'),
            ('paid', 'Paid'),
            ('partial', 'Partial'),
            ('reversed', 'Reversed'),
            ('invoicing_legacy', 'Invoicing App Legacy'),
        ],
        string='Invoice State / حالة الفاتورة',
        related='invoice_id.payment_state',
        readonly=True,
    )

    # ── Computed counts ───────────────────────────────────────────────────
    vital_count: fields.Integer = fields.Integer(
        compute='_compute_vital_count',
        string='Vitals',
    )
    prescription_count: fields.Integer = fields.Integer(
        compute='_compute_prescription_count',
        string='Prescriptions',
    )
    lab_request_count: fields.Integer = fields.Integer(
        compute='_compute_lab_request_count',
        string='Lab Requests',
    )

    def _compute_vital_count(self) -> None:
        for rec in self:
            rec.vital_count = len(rec.vital_sign_ids)

    def _compute_prescription_count(self) -> None:
        for rec in self:
            rec.prescription_count = len(rec.prescription_ids)

    def _compute_lab_request_count(self) -> None:
        for rec in self:
            rec.lab_request_count = len(rec.lab_request_ids)

    # ── ORM hooks ─────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> 'HealthEncounter':
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('encounter_number', 'New') == 'New':
                vals['encounter_number'] = seq.next_by_code(
                    'health.encounter'
                ) or 'New'
        return super().create(vals_list)

    # ── Constraints ───────────────────────────────────────────────────────

    @api.constrains('state', 'vital_sign_ids', 'chief_complaint')
    def _check_done_prerequisites(self) -> None:
        """Transitioning to done requires vitals and chief complaint.

        الانتقال إلى "منتهٍ" يتطلب علامات حيوية وشكوى رئيسية.
        """
        for rec in self:
            if rec.state == 'done':
                if not rec.chief_complaint:
                    raise ValidationError(
                        'Chief complaint is required before completing the encounter.\n'
                        'الشكوى الرئيسية مطلوبة قبل إتمام الزيارة.'
                    )
                if not rec.vital_sign_ids:
                    raise ValidationError(
                        'At least one vital sign reading is required before '
                        'completing the encounter.\n'
                        'مطلوب إدخال قراءة واحدة على الأقل للعلامات الحيوية قبل الإتمام.'
                    )

    # ── State transitions ─────────────────────────────────────────────────

    def action_start(self) -> None:
        """Start encounter: draft → in_progress.

        بدء الزيارة: مسودة → جارٍ.
        """
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    'Only draft encounters can be started.\n'
                    'يمكن بدء الزيارات في المسودة فقط.'
                )
            rec.write({'state': 'in_progress'})

    def action_done(self) -> None:
        """Complete encounter: in_progress → done.

        إتمام الزيارة: جارٍ → منتهٍ.
        """
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(
                    'Only in-progress encounters can be completed.\n'
                    'يمكن إتمام الزيارات الجارية فقط.'
                )
            if not rec.chief_complaint:
                raise UserError(
                    'Please enter the chief complaint before completing.\n'
                    'الرجاء إدخال الشكوى الرئيسية قبل الإتمام.'
                )
            if not rec.vital_sign_ids:
                raise UserError(
                    'Please record at least one vital sign before completing.\n'
                    'الرجاء تسجيل علامة حيوية واحدة على الأقل قبل الإتمام.'
                )
            rec.write({'state': 'done'})
            # Sync linked appointment
            if rec.appointment_id and rec.appointment_id.state == 'in_progress':
                rec.appointment_id.write({'state': 'done'})

    def action_invoice(self) -> dict:
        """Post consultation invoice: done → invoiced.

        ترحيل فاتورة الاستشارة: منتهٍ → مفوتر.

        Uses the specialty consultation product (OQ-02 decision).
        يستخدم منتج الاستشارة الخاص بالتخصص (قرار OQ-02).
        """
        self.ensure_one()
        if self.state != 'done':
            raise UserError(
                'Encounter must be completed before invoicing.\n'
                'يجب إتمام الزيارة قبل الفوترة.'
            )
        if self.invoice_id:
            raise UserError(
                'This encounter has already been invoiced.\n'
                'هذه الزيارة مفوترة بالفعل.'
            )

        # Resolve consultation product from specialty (OQ-02)
        specialty = self.doctor_id.specialty_id
        product = specialty.consultation_product_id if specialty else False
        if not product:
            raise UserError(
                f'No consultation product is configured for specialty '
                f'"{specialty.name if specialty else "—"}".\n'
                f'Go to: Health > Configuration > Specialties and set a '
                f'Consultation Product.\n'
                f'لم يتم تهيئة منتج استشارة للتخصص '
                f'"{specialty.name if specialty else "—"}".'
            )

        # Build invoice
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.patient_id.partner_id.id,
            'company_id': self.company_id.id,
            'invoice_date': fields.Date.today(),
            'ref': self.encounter_number,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'name': (
                    f'[{self.encounter_number}] '
                    f'Consultation — {specialty.name}'
                ),
                'quantity': 1.0,
                'price_unit': product.lst_price,
                'tax_ids': [(6, 0, product.taxes_id.ids)],
            })],
        }
        invoice = self.env['account.move'].create(invoice_vals)
        self.write({'invoice_id': invoice.id, 'state': 'invoiced'})

        # Return the invoice form for review
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice / الفاتورة',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self) -> None:
        """Cancel encounter.

        إلغاء الزيارة.
        """
        for rec in self:
            if rec.state == 'invoiced':
                raise UserError(
                    'Invoiced encounters cannot be cancelled. '
                    'Please cancel the invoice first.\n'
                    'لا يمكن إلغاء الزيارات المفوترة. يرجى إلغاء الفاتورة أولاً.'
                )
            rec.write({'state': 'cancelled'})

    # ── Smart button actions ───────────────────────────────────────────────

    def action_view_invoice(self) -> dict:
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }

    def action_new_prescription(self) -> dict:
        """Open a full-page new prescription form linked to this encounter.

        فتح نموذج وصفة جديدة في صفحة كاملة مرتبطة بهذه الزيارة.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'New Prescription / وصفة جديدة',
            'res_model': 'health.prescription',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_encounter_id': self.id,
                'default_patient_id': self.patient_id.id,
                'default_doctor_id': self.doctor_id.id,
            },
        }

