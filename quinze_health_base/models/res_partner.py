# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
Partner Extension — Medical Roles & Patient Demographics
امتداد الشريك — الأدوار الطبية والبيانات الديموغرافية للمريض

Extends res.partner with:
  - Boolean role flags: is_patient, is_doctor, is_pharmacist, is_lab_tech
  - Doctor fields: specialty_id, medical_license_no
  - Patient demographics: national_id, dob, gender, blood_type,
    emergency contact, allergies (m2m)

يمدّ نموذج res.partner بأعلام الأدوار الطبية وحقول المريض الديموغرافية.
"""
from __future__ import annotations

from datetime import date as _date

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    """Extend res.partner with QUINZE Health medical fields.

    امتداد res.partner بحقول نظام QUINZE الصحي.
    """

    _inherit = 'res.partner'

    # ═══════════════════════════════════════════════════════════════════════
    # Role flags
    # ═══════════════════════════════════════════════════════════════════════

    is_patient: fields.Boolean = fields.Boolean(
        string='Is Patient / مريض',
        default=False,
        index=True,
        tracking=True,
        help=(
            'Mark this contact as a patient. '
            'A health.patient record will be created automatically.\n'
            'تحديد هذا الاتصال كمريض. سيتم إنشاء سجل health.patient تلقائياً.'
        ),
    )
    is_doctor: fields.Boolean = fields.Boolean(
        string='Is Doctor / طبيب',
        default=False,
        index=True,
        tracking=True,
    )
    is_pharmacist: fields.Boolean = fields.Boolean(
        string='Is Pharmacist / صيدلاني',
        default=False,
        index=True,
    )
    is_lab_tech: fields.Boolean = fields.Boolean(
        string='Is Lab Technician / تقني مختبر',
        default=False,
        index=True,
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Doctor-specific fields
    # ═══════════════════════════════════════════════════════════════════════

    specialty_id: fields.Many2one = fields.Many2one(
        comodel_name='health.specialty',
        string='Specialty / التخصص',
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    medical_license_no: fields.Char = fields.Char(
        string='Medical License No. / رقم الترخيص الطبي',
        size=50,
        tracking=True,
        copy=False,
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Patient demographics
    # ═══════════════════════════════════════════════════════════════════════

    national_id: fields.Char = fields.Char(
        string='National ID / رقم الهوية الوطنية',
        size=20,
        index=True,
        tracking=True,
        copy=False,
        help=(
            'Saudi National ID (10 digits) or Iqama number.\n'
            'رقم الهوية الوطنية السعودية (10 أرقام) أو رقم الإقامة.'
        ),
    )
    dob: fields.Date = fields.Date(
        string='Date of Birth / تاريخ الميلاد',
        tracking=True,
    )
    age: fields.Integer = fields.Integer(
        string='Age / العمر',
        compute='_compute_age',
        store=True,
        help='Computed from Date of Birth. / محسوب من تاريخ الميلاد.',
    )
    gender: fields.Selection = fields.Selection(
        selection=[
            ('male',   'Male / ذكر'),
            ('female', 'Female / أنثى'),
            ('other',  'Other / أخرى'),
        ],
        string='Gender / الجنس',
        index=True,
        tracking=True,
    )
    blood_type: fields.Selection = fields.Selection(
        selection=[
            ('A+', 'A+'), ('A-', 'A-'),
            ('B+', 'B+'), ('B-', 'B-'),
            ('AB+', 'AB+'), ('AB-', 'AB-'),
            ('O+', 'O+'),  ('O-', 'O-'),
        ],
        string='Blood Type / فصيلة الدم',
        tracking=True,
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Emergency contact
    # ═══════════════════════════════════════════════════════════════════════

    emergency_contact_name: fields.Char = fields.Char(
        string='Emergency Contact Name / اسم جهة الطوارئ',
        size=100,
    )
    emergency_contact_phone: fields.Char = fields.Char(
        string='Emergency Contact Phone / هاتف جهة الطوارئ',
        size=20,
    )
    emergency_contact_relation: fields.Char = fields.Char(
        string='Relation / صلة القرابة',
        size=50,
        help=(
            'Relationship to the patient (e.g. Father, Spouse).\n'
            'صلة القرابة بالمريض (مثل: والد، زوج).'
        ),
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Allergies (m2m — shared catalog)
    # ═══════════════════════════════════════════════════════════════════════

    allergies_ids: fields.Many2many = fields.Many2many(
        comodel_name='health.allergy',
        relation='partner_health_allergy_rel',
        column1='partner_id',
        column2='allergy_id',
        string='Known Allergies / الحساسيات المعروفة',
        tracking=True,
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Computed fields
    # ═══════════════════════════════════════════════════════════════════════

    @api.depends('dob')
    def _compute_age(self) -> None:
        """Compute integer age in years from date of birth.

        حساب العمر بالسنوات من تاريخ الميلاد.
        """
        today = _date.today()
        for rec in self:
            if rec.dob:
                rec.age = (
                    today.year - rec.dob.year
                    - (
                        (today.month, today.day)
                        < (rec.dob.month, rec.dob.day)
                    )
                )
            else:
                rec.age = 0

    # ═══════════════════════════════════════════════════════════════════════
    # Constraints
    # ═══════════════════════════════════════════════════════════════════════

    @api.constrains('national_id', 'is_patient')
    def _check_national_id_unique(self) -> None:
        """National ID must be unique among patients in the same company.

        رقم الهوية الوطنية يجب أن يكون فريداً بين المرضى في نفس الشركة.
        """
        for rec in self:
            if not (rec.is_patient and rec.national_id):
                continue
            duplicate = self.search_count([
                ('is_patient', '=', True),
                ('national_id', '=', rec.national_id),
                ('company_id', '=', rec.company_id.id),
                ('id', '!=', rec.id),
            ])
            if duplicate:
                raise ValidationError(
                    f'National ID "{rec.national_id}" is already registered '
                    f'for another patient in this company.\n'
                    f'رقم الهوية "{rec.national_id}" مسجّل لمريض آخر في هذه الشركة.'
                )

    @api.constrains('dob')
    def _check_dob(self) -> None:
        """Date of birth must not be in the future.

        تاريخ الميلاد يجب ألا يكون في المستقبل.
        """
        today = _date.today()
        for rec in self:
            if rec.dob and rec.dob > today:
                raise ValidationError(
                    'Date of birth cannot be in the future.\n'
                    'تاريخ الميلاد لا يمكن أن يكون في المستقبل.'
                )

    # ═══════════════════════════════════════════════════════════════════════
    # Onchange helpers
    # ═══════════════════════════════════════════════════════════════════════

    @api.onchange('is_doctor')
    def _onchange_is_doctor(self) -> None:
        """Clear specialty when doctor flag is removed.

        مسح التخصص عند إزالة علامة الطبيب.
        """
        if not self.is_doctor:
            self.specialty_id = False
            self.medical_license_no = False
