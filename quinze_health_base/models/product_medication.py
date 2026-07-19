# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
product.template / product.product — Medication Flag
=====================================================
علامة الدواء على المنتج

Adds the ``is_medication`` Boolean flag to **both** product.template and
product.product so that any module (clinic, pharmacy …) can safely use:

    domain="[('is_medication', '=', True)]"

regardless of whether quinze_health_pharmacy is installed.

يضيف علامة ``is_medication`` لكلا النموذجين product.template و product.product
حتى يمكن استخدام الـ domain في أي وحدة بأمان حتى لو لم تُثبَّت وحدة الصيدلة.
"""

from odoo import fields, models


class ProductTemplateMedication(models.Model):
    _inherit = "product.template"

    is_medication = fields.Boolean(
        string="Is Medication / دواء",
        default=False,
        help=(
            "Flag this product as a dispensable medication.\n"
            "تمييز هذا المنتج كدواء قابل للصرف."
        ),
    )


class ProductProductMedication(models.Model):
    """Expose is_medication on the variant model so domain filters work."""

    _inherit = "product.product"

    is_medication = fields.Boolean(
        related="product_tmpl_id.is_medication",
        string="Is Medication / دواء",
        store=True,
        readonly=True,
    )
