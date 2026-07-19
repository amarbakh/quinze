# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
ICD-10 Diagnosis Codes
رموز التشخيص ICD-10

Lite subset of ICD-10 codes preloaded from data/icd10_data.xml.
Used as a many2many on health.encounter for recording diagnoses.

مجموعة محدودة من رموز ICD-10 محملة مسبقاً من ملف البيانات.
تُستخدم كعلاقة m2m على نموذج الزيارة لتسجيل التشخيصات.
"""
from __future__ import annotations

from odoo import api, fields, models


class HealthIcd10(models.Model):
    """ICD-10 diagnosis code (lite catalog).

    رمز تشخيص ICD-10 (كتالوج مختصر).
    """

    _name = 'health.icd10'
    _description = 'ICD-10 Diagnosis Code / رمز تشخيص ICD-10'
    _order = 'code'
    _rec_name = 'display_name'

    # ── ICD-10 chapters ───────────────────────────────────────────────────
    ICD10_CHAPTER = [
        ('I',     'I — Infectious & Parasitic / الأمراض المعدية والطفيلية'),
        ('II',    'II — Neoplasms / الأورام'),
        ('III',   'III — Blood Diseases / أمراض الدم'),
        ('IV',    'IV — Endocrine & Metabolic / الغدد الصماء والتمثيل الغذائي'),
        ('V',     'V — Mental & Behavioural / الاضطرابات النفسية والسلوكية'),
        ('VI',    'VI — Nervous System / الجهاز العصبي'),
        ('VII',   'VII — Eye & Adnexa / العين وملحقاتها'),
        ('VIII',  'VIII — Ear / الأذن'),
        ('IX',    'IX — Circulatory / الجهاز الدوري'),
        ('X',     'X — Respiratory / الجهاز التنفسي'),
        ('XI',    'XI — Digestive / الجهاز الهضمي'),
        ('XII',   'XII — Skin / الجلد'),
        ('XIII',  'XIII — Musculoskeletal / الجهاز العضلي الهيكلي'),
        ('XIV',   'XIV — Genitourinary / الجهاز البولي التناسلي'),
        ('XV',    'XV — Pregnancy & Childbirth / الحمل والولادة'),
        ('XVI',   'XVI — Perinatal / الفترة المحيطة بالولادة'),
        ('XVII',  'XVII — Congenital / التشوهات الخلقية'),
        ('XVIII', 'XVIII — Symptoms & Signs / الأعراض والعلامات'),
        ('XIX',   'XIX — Injury & Poisoning / الإصابات والتسمم'),
        ('XXI',   'XXI — Factors Influencing Health / عوامل مؤثرة على الصحة'),
    ]

    # ── Fields ───────────────────────────────────────────────────────────
    code: fields.Char = fields.Char(
        string='Code / الرمز',
        required=True,
        size=10,
        index=True,
    )
    name_en: fields.Char = fields.Char(
        string='Description (EN) / الوصف (إنجليزي)',
        required=True,
        index=True,
    )
    name_ar: fields.Char = fields.Char(
        string='Description (AR) / الوصف (عربي)',
        index=True,
    )
    chapter: fields.Selection = fields.Selection(
        selection=ICD10_CHAPTER,
        string='Chapter / الفصل',
        index=True,
    )
    active: fields.Boolean = fields.Boolean(
        string='Active / نشط',
        default=True,
    )

    # ── Computed display name (bilingual, language-aware) ─────────────────
    display_name: fields.Char = fields.Char(
        string='Display Name / الاسم المعروض',
        compute='_compute_display_name',
        store=True,           # store=True so it's searchable / filterable
        index=True,
    )

    @api.depends('code', 'name_en', 'name_ar')
    def _compute_display_name(self) -> None:
        """Build bilingual display name: CODE — AR (or EN if AR missing).

        بناء الاسم المعروض ثنائي اللغة: الرمز — العربي (أو الإنجليزي إن غاب العربي).
        """
        for rec in self:
            desc = rec.name_ar or rec.name_en or ''
            rec.display_name = f'{rec.code} — {desc}' if desc else rec.code

    # noinspection PyMethodMayBeStatic
    def name_get(self) -> list[tuple[int, str]]:
        """Show CODE — localised description in dropdowns.

        عرض الرمز — الوصف المحلي في القوائم المنسدلة.
        """
        lang = self.env.lang or 'en_US'
        result = []
        for rec in self:
            if lang.startswith('ar') and rec.name_ar:
                label = f'{rec.code} — {rec.name_ar}'
            else:
                label = f'{rec.code} — {rec.name_en}'
            result.append((rec.id, label))
        return result

    @api.model
    def _name_search(
        self,
        name: str = '',
        domain: list | None = None,
        operator: str = 'ilike',
        limit: int = 100,
        order: str | None = None,
    ):
        """Search by code OR description (EN/AR).

        البحث برمز ICD-10 أو الوصف (إنجليزي/عربي).
        """
        domain = list(domain or [])
        if name:
            domain = [
                '|', '|',
                ('code', operator, name),
                ('name_en', operator, name),
                ('name_ar', operator, name),
            ] + domain
        return self._search(domain, limit=limit, order=order)

    # ── Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'code_unique',
            'UNIQUE(code)',
            'ICD-10 code must be unique. / رمز ICD-10 يجب أن يكون فريداً.',
        ),
    ]
