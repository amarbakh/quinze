# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License OPL-1 (Odoo Proprietary License v1.0)
{
    'name': 'QUINZE Health API',
    'summary': 'JSON REST API for QUINZE Health Suite — Clinic, Lab & Pharmacy',
    'description': """
QUINZE Health API / واجهة برمجة التطبيقات لنظام QUINZE الصحي
==============================================================
Provides authenticated JSON REST endpoints for all three modules:

**Base URL:** ``/api/quinze/v1/``

**Authentication / المصادقة:**
  HTTP header ``X-API-Key: <key>`` — keys are managed in
  Settings → Technical → API Keys / إدارة مفاتيح API

**Clinic endpoints / نقاط نهاية العيادة:**
  GET  /patients               — list patients (paginated)
  GET  /patients/<id>          — patient detail
  GET  /appointments           — list appointments
  POST /appointments           — create appointment
  GET  /appointments/<id>      — appointment detail + encounter summary
  GET  /prescriptions          — list prescriptions
  GET  /prescriptions/<id>     — prescription detail with lines

**Lab endpoints / نقاط نهاية المختبر:**
  GET  /lab/orders             — list lab orders
  GET  /lab/orders/<id>        — order detail with results
  POST /lab/orders/<id>/result — submit a single test result

**Pharmacy endpoints / نقاط نهاية الصيدلية:**
  GET  /pharmacy/dispensings        — list dispensings
  POST /pharmacy/dispensings        — create external dispensing
  GET  /pharmacy/dispensings/<id>   — dispensing detail
  POST /pharmacy/dispensings/<id>/confirm  — confirm dispensing
  GET  /pharmacy/claims             — list insurance claims

**Response envelope / مغلف الاستجابة:**
  Success: ``{"status": "ok", "data": {...}, "meta": {"total": n, "page": p}}``
  Error:   ``{"status": "error", "code": 400, "message": "..."}``
    """,
    'version': '17.0.1.0.0',
    'category': 'Health',
    'author': 'Bakhit Alamin',
    'license': 'OPL-1',
    'support': 'amarnew198611@gmail.com',
    'maintainer': 'Bakhit Alamin',
    'images': ['static/description/banner.png'],
    'price': 99.0,
    'currency': 'EUR',

    'depends': [
        'quinze_health_clinic',
        'quinze_health_lab',
        'quinze_health_pharmacy',
        'web',
    ],

    'data': [
        'security/ir.model.access.csv',
        'data/api_key_group.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}
