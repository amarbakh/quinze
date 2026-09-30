# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License OPL-1 (Odoo Proprietary License v1.0)
{
    'name': 'QUINZE Health Lab',
    'summary': (
        'Laboratory test catalog, orders, sample tracking, '
        'results with reference ranges and bilingual PDF report'
    ),
    'description': """
QUINZE Health Lab / مختبر نظام QUINZE الصحي
=============================================
Provides the laboratory workflow layer of the QUINZE Health Suite:

* **Test Catalog** — Categories (Hematology, Chemistry, etc.) and individual
  test definitions with gender/age-specific reference ranges and critical limits.
* **Lab Orders** — Created automatically when a ``health.lab.request`` is
  confirmed (bridge hook override). Workflow:
  draft → sample_collected → in_progress → done / cancelled
* **Sample Tracking** — ``lab.sample`` model tracks type, collection time,
  collector, and state (pending → collected → received → rejected).
* **Results with Flags** — Each result is compared to the reference range
  (patient gender-specific). Flags: normal / high / low / critical_high /
  critical_low. Auto-validated when all lines are resulted.
* **Lab Report PDF** — Bilingual (AR/EN), RTL-aware, highlights abnormal values
  in colour with reference ranges printed alongside each result.
* **Bridge Override** — Inherits ``health.lab.request`` to override
  ``_action_create_lab_order()`` (no-op in clinic, real creation here).

يوفر هذا الموديول طبقة سير العمل المخبري:
كتالوج الفحوصات، أوامر المختبر، تتبع العينات،
النتائج مع النطاقات المرجعية، تقرير PDF ثنائي اللغة.
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
        'quinze_health_clinic',   # health.lab.request bridge lives here
    ],

    'data': [
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/lab_test_categories.xml',
        # Views: actions must be defined before the menus that reference them
        'views/lab_test_category_views.xml',
        'views/lab_test_views.xml',
        'views/lab_sample_views.xml',
        'views/lab_order_views.xml',
        'views/health_lab_request_views.xml',
        'views/menus.xml',
        'reports/lab_report.xml',
    ],

    'demo': [
        'demo/demo_data.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}
