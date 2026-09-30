# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
{
    'name': 'QUINZE Health Base',
    'summary': (
        'Shared base layer for QUINZE Health Suite '
        '(Clinic, Laboratory, Pharmacy)'
    ),
    'description': """
QUINZE Health Base / قاعدة نظام QUINZE الصحي
=============================================
Provides the shared foundation for all QUINZE Health Suite modules:

* Security groups (User / Doctor / Lab Tech / Pharmacist / Manager / Admin)
* Abstract ``health.mixin`` with company_id, active, note, branch_id
* ``res.partner`` extension: medical role flags + patient demographics
* Master data: specialties, allergies, ICD-10 (lite), medical UoM, branches
* Numbered sequences for all transactional documents (per-company)
* Full Arabic i18n (ar_001) with RTL-aware base views
* Demo data with Arabic-named sample records

يوفر هذا الموديول البنية التحتية المشتركة لجميع وحدات نظام QUINZE الصحي:
مجموعات الأمان، النماذج المجردة، بيانات الشركاء الطبية، البيانات الرئيسية،
التسلسلات، الترجمة العربية، والبيانات التجريبية.
    """,
    'version': '17.0.1.0.0',
    'category': 'Health',
    'author': 'Bakhit Alamin',
    'license': 'LGPL-3',
    'support': 'amarnew198611@gmail.com',
    'maintainer': 'Bakhit Alamin',
    'images': ['static/description/banner.png'],

    # ── Odoo standard dependencies only ──────────────────────────────────
    'depends': [
        'base',
        'mail',
        'account',
        'product',
    ],

    # ── Data files loaded IN ORDER ────────────────────────────────────────
    'data': [
        # 1. Security first (groups must exist before access rules)
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        # 2. Static data
        'data/sequences.xml',
        'data/icd10_data.xml',
        'data/medical_uom_data.xml',
        # 3. Views (actions must be defined BEFORE menus that reference them)
        'views/res_partner_views.xml',
        'views/master_data_views.xml',
        'views/menus.xml',
    ],

    'demo': [
        'demo/demo_data.xml',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,

    # Enterprise feature-flag: set to True if web_enterprise is installed
    # Checked at runtime in models/health_mixin.py
    # 'enterprise_depends': ['web_enterprise'],  # informational only
}
