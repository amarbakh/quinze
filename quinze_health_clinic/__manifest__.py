# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License OPL-1 (Odoo Proprietary License v1.0)
{
    'name': 'QUINZE Health Clinic',
    'summary': (
        'Patient management, appointments, encounters, '
        'prescriptions and lab requests'
    ),
    'description': """
QUINZE Health Clinic / عيادة نظام QUINZE الصحي
===============================================
Provides the clinical workflow layer of the QUINZE Health Suite:

* **Patients** — One-to-one with res.partner; full medical history,
  allergies, chronic conditions, computed age.
* **Appointments** — Free datetime scheduling with doctor/room conflict
  prevention. Calendar + Kanban views.
* **Encounters** — The visit itself: vitals, ICD-10 diagnoses,
  clinical notes. Workflow: draft → in_progress → done → invoiced.
  Invoicing posts an ``account.move`` using the specialty consultation
  product (per-specialty pricing, OQ-02).
* **Prescriptions** — Drug / dose / frequency / duration / route with
  full dispensing-status tracking.
* **Lab Requests** — Bridge to quinze_health_lab; creates a lab.order
  on confirmation when the lab module is installed.
* **Portal** — Patients view their own appointments and prescriptions
  via the standard Odoo portal (``/my/health/``).
* **QWeb Report** — Bilingual (AR/EN), RTL-aware prescription PDF.

يوفر هذا الموديول طبقة سير العمل السريرية:
المرضى، المواعيد، الزيارات، الوصفات الطبية، طلبات المختبر.
    """,
    'version': '17.0.1.0.0',
    'category': 'Health',
    'author': 'Bakhit Alamin',
    'license': 'OPL-1',
    'support': 'amarnew198611@gmail.com',
    'maintainer': 'Bakhit Alamin',
    'images': ['static/description/banner.png'],
    'price': 149.0,
    'currency': 'EUR',

    'depends': [
        'quinze_health_base',
        'account',      # invoice posting on encounter completion
        'calendar',     # appointment calendar view
        'portal',       # patient portal (/my/health/)
    ],

    'data': [
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/clinic_products.xml',
        # Views: actions must be defined before the menus that reference them
        'views/health_room_views.xml',
        'views/health_patient_views.xml',
        'views/health_prescription_views.xml',   # must load before encounter (action ref)
        'views/health_lab_request_views.xml',
        'views/health_appointment_views.xml',
        'views/health_encounter_views.xml',
        'views/portal_templates.xml',
        'views/menus.xml',
        'reports/prescription_report.xml',
    ],

    'demo': [
        'demo/demo_data.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}
