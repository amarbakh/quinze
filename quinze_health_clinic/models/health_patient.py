# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
"""
Health Patient
سجل المريض

Separate model (per OQ-01 decision) with a Many2one FK to res.partner.
Carries the patient number (sequence), full medical history, and exposes
partner demographics as related fields for convenience.

نموذج منفصل (وفق قرار OQ-01) بمفتاح خارجي لـ res.partner.
يحمل رقم المريض (تسلسل) والتاريخ الطبي الكامل.
"""
from __future__ import annotations

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HealthPatient(models.Model):
    """Patient record — one-to-one with res.partner.

    سجل المريض — علاقة واحد لواحد مع res.partner.
    """

    _name = 'health.patient'
    _description = 'Patient / مريض'
    _inherit = ['health.mixin']
    _order = 'patient_number desc'
    _rec_name = 'display_name'

    # ── Core identity ─────────────────────────────────────────────────────
    partner_id: fields.Many2one = fields.Many2one(
        comodel_name='res.partner',
        string='Contact / جهة الاتصال',
        required=True,
        ondelete='restrict',
        index=True,
        domain="[('is_patient', '=', True)]",
        tracking=True,
        help=(
            'The partner record for this patient. '
            'Must have is_patient=True.\n'
            'سجل الشريك لهذا المريض. يجب أن يكون is_patient=True.'
        ),
    )
    patient_number: fields.Char = fields.Char(
        string='Patient No. / رقم المريض',
        readonly=True,
        copy=False,
        index=True,
        default='New',
        tracking=True,
    )
    display_name: fields.Char = fields.Char(
        string='Patient / المريض',
        compute='_compute_display_name',
        store=True,
        index=True,
    )

    # ── Related partner fields (read-only convenience) ────────────────────
    name: fields.Char = fields.Char(
        related='partner_id.name',
        string='Name / الاسم',
        store=True,
        readonly=True,
        index=True,
    )
    national_id: fields.Char = fields.Char(
        related='partner_id.national_id',
        string='National ID / رقم الهوية',
        store=True,
        readonly=True,
    )
    dob: fields.Date = fields.Date(
        related='partner_id.dob',
        string='Date of Birth / تاريخ الميلاد',
        readonly=True,
    )
    age: fields.Integer = fields.Integer(
        related='partner_id.age',
        string='Age / العمر',
        store=True,
        readonly=True,
    )
    gender: fields.Selection = fields.Selection(
        related='partner_id.gender',
        string='Gender / الجنس',
        readonly=True,
        store=True,
    )
    blood_type: fields.Selection = fields.Selection(
        related='partner_id.blood_type',
        string='Blood Type / فصيلة الدم',
        readonly=True,
    )
    allergies_ids: fields.Many2many = fields.Many2many(
        related='partner_id.allergies_ids',
        string='Allergies / الحساسيات',
        readonly=True,
    )
    phone: fields.Char = fields.Char(
        related='partner_id.phone',
        string='Phone / الهاتف',
        readonly=True,
    )
    mobile: fields.Char = fields.Char(
        related='partner_id.mobile',
        string='Mobile / الجوال',
        readonly=True,
    )

    # ── Medical history ───────────────────────────────────────────────────
    medical_history: fields.Text = fields.Text(
        string='Medical History / التاريخ الطبي',
        help='Summary of past illnesses, surgeries, hospitalizations.\n'
             'ملخص الأمراض السابقة والعمليات والتنويم.',
    )
    chronic_conditions: fields.Text = fields.Text(
        string='Chronic Conditions / الأمراض المزمنة',
        help='Ongoing diagnoses (e.g. DM, HTN, CKD).\n'
             'التشخيصات الجارية (مثل: السكري، ضغط الدم، القصور الكلوي).',
    )
    family_history: fields.Text = fields.Text(
        string='Family History / التاريخ العائلي',
    )
    surgical_history: fields.Text = fields.Text(
        string='Surgical History / التاريخ الجراحي',
    )

    # ── Smart-button counters ─────────────────────────────────────────────
    appointment_count: fields.Integer = fields.Integer(
        string='Appointments / المواعيد',
        compute='_compute_appointment_count',
    )
    encounter_count: fields.Integer = fields.Integer(
        string='Encounters / الزيارات',
        compute='_compute_encounter_count',
    )
    prescription_count: fields.Integer = fields.Integer(
        string='Prescriptions / الوصفات',
        compute='_compute_prescription_count',
    )

    # ── Computed ──────────────────────────────────────────────────────────

    @api.depends('patient_number', 'partner_id.name')
    def _compute_display_name(self) -> None:
        """Display as 'PAT/YYYY/XXXXX — Full Name'.

        عرض بصيغة 'رقم المريض — الاسم الكامل'.
        """
        for rec in self:
            num = rec.patient_number or 'New'
            name = rec.partner_id.name or ''
            rec.display_name = f'{num} — {name}' if name else num

    def _compute_appointment_count(self) -> None:
        for rec in self:
            rec.appointment_count = self.env['health.appointment'].search_count(
                [('patient_id', '=', rec.id)]
            )

    def _compute_encounter_count(self) -> None:
        for rec in self:
            rec.encounter_count = self.env['health.encounter'].search_count(
                [('patient_id', '=', rec.id)]
            )

    def _compute_prescription_count(self) -> None:
        for rec in self:
            rec.prescription_count = self.env['health.prescription'].search_count(
                [('patient_id', '=', rec.id)]
            )

    # ── ORM hooks ─────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> 'HealthPatient':
        """Assign patient number from sequence on creation.

        تعيين رقم المريض من التسلسل عند الإنشاء.
        """
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('patient_number', 'New') == 'New':
                vals['patient_number'] = seq.next_by_code('health.patient') or 'New'
        return super().create(vals_list)

    # ── Constraints ───────────────────────────────────────────────────────

    @api.constrains('partner_id', 'company_id')
    def _check_partner_unique(self) -> None:
        """One patient record per partner per company.

        سجل مريض واحد لكل شريك لكل شركة.
        """
        for rec in self:
            dup = self.search_count([
                ('partner_id', '=', rec.partner_id.id),
                ('company_id', '=', rec.company_id.id),
                ('id', '!=', rec.id),
            ])
            if dup:
                raise ValidationError(
                    f'Partner "{rec.partner_id.name}" already has a patient '
                    f'record in this company.\n'
                    f'الشريك "{rec.partner_id.name}" لديه سجل مريض بالفعل في هذه الشركة.'
                )

    # ── Actions (smart buttons) ────────────────────────────────────────────

    def action_view_appointments(self) -> dict:
        """Open appointment list filtered to this patient.

        فتح قائمة المواعيد مفلترة لهذا المريض.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'Appointments / المواعيد',
            'res_model': 'health.appointment',
            'view_mode': 'tree,calendar,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }

    def action_view_encounters(self) -> dict:
        """Open encounter list filtered to this patient.

        فتح قائمة الزيارات مفلترة لهذا المريض.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'Encounters / الزيارات',
            'res_model': 'health.encounter',
            'view_mode': 'tree,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }
