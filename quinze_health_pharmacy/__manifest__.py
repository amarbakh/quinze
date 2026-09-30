# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License OPL-1 (Odoo Proprietary License v1.0)
{
    'name': 'QUINZE Health Pharmacy',
    'summary': (
        'Internal & external pharmacy dispensing, stock integration, '
        'automatic invoicing and insurance claim management'
    ),
    'description': """
QUINZE Health Pharmacy / صيدلية نظام QUINZE الصحي
===================================================
Provides the pharmacy workflow layer of the QUINZE Health Suite.

**Two dispensing modes / نمطا الصرف:**

* **Internal / داخلي** — Triggered from a confirmed ``health.prescription``
  originating in the clinic. Lines are pre-populated from the prescription,
  quantities are validated, and the prescription state is updated to
  *partially_dispensed* or *dispensed* upon completion.

* **External / خارجي** — Walk-in customers or patients with external
  prescriptions. Full drug selection, pricing, and automatic ``account.move``
  creation on confirmation.

**Stock integration / تكامل المخزون:**
  Each dispensing creates a ``stock.picking`` (outgoing) from the dedicated
  pharmacy stock location. Lot / expiry-date tracking is supported via
  standard Odoo ``stock.lot``.

**Insurance claims / مطالبات التأمين:**
  Full ``pharmacy.insurance.claim`` workflow:
  draft → submitted → approved / rejected.
  Coverage percentage reduces the patient-facing invoice amount.

**Product extension / تمديد المنتج:**
  Adds ``is_medication``, ``generic_name_ar``, ``dosage_form``, ``strength``,
  and ``drug_category_id`` to ``product.template``.

يوفر هذا الموديول طبقة سير العمل الصيدلاني:
الصرف الداخلي والخارجي، تكامل المخزون،
إنشاء الفواتير التلقائي، وإدارة مطالبات التأمين.
    """,
    'version': '17.0.1.0.0',
    'category': 'Health',
    'author': 'Bakhit Alamin',
    'license': 'OPL-1',
    'support': 'amarnew198611@gmail.com',
    'maintainer': 'Bakhit Alamin',
    'images': ['static/description/banner.png'],
    'price': 129.0,
    'currency': 'EUR',

    'depends': [
        'quinze_health_clinic',   # health.prescription lives here
        'stock',                  # stock.picking / stock.location
        'account',                # account.move for external sales
    ],

    'data': [
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/pharmacy_data.xml',
        # Views: actions must be defined before the menus that reference them
        'views/product_views.xml',
        'views/pharmacy_dispensing_views.xml',
        'views/pharmacy_insurance_claim_views.xml',
        'views/health_prescription_views.xml',
        'views/menus.xml',
        'reports/dispensing_receipt.xml',
    ],

    'demo': [
        'demo/demo_data.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}
