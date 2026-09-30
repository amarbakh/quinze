# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
product.template — Pharmacy-Specific Extension
===============================================
تمديد المنتج للصيدلة

Adds pharmacy-specific fields to Odoo's product.template.
NOTE: is_medication is defined in quinze_health_base so that the clinic
module (which doesn't depend on pharmacy) can use the domain safely.

يضيف حقولاً خاصة بالصيدلة لنموذج product.template.
ملاحظة: حقل is_medication مُعرَّف في quinze_health_base ليكون متاحاً
لوحدة العيادة التي لا تعتمد على وحدة الصيدلة.
"""

from odoo import fields, models

DOSAGE_FORM_SELECTION = [
    ("tablet", "Tablet / قرص"),
    ("capsule", "Capsule / كبسولة"),
    ("syrup", "Syrup / شراب"),
    ("injection", "Injection / حقنة"),
    ("cream", "Cream / كريم"),
    ("ointment", "Ointment / مرهم"),
    ("drops", "Drops / قطرات"),
    ("inhaler", "Inhaler / بخاخ"),
    ("patch", "Patch / لاصق جلدي"),
    ("suppository", "Suppository / تحميلة"),
    ("powder", "Powder / مسحوق"),
    ("solution", "Solution / محلول"),
    ("other", "Other / أخرى"),
]


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # is_medication is inherited from quinze_health_base.product_medication
    # No re-declaration here to avoid duplicate field errors.

    # ── Drug identification ───────────────────────────────────────────────────
    generic_name_ar = fields.Char(
        string="Generic Name (AR) / الاسم العلمي",
        help="Generic/scientific name in Arabic for prescription printout. / "
             "الاسم العلمي بالعربية للوصفة الطبية.",
    )
    drug_category_id = fields.Many2one(
        comodel_name="pharmacy.drug.category",
        string="Drug Category / تصنيف الدواء",
        ondelete="set null",
        tracking=True,
    )
    dosage_form = fields.Selection(
        selection=DOSAGE_FORM_SELECTION,
        string="Dosage Form / الشكل الصيدلاني",
        tracking=True,
    )
    strength = fields.Char(
        string="Strength / التركيز",
        help="e.g. 500 mg, 5 mg/5 mL, 0.1% / مثال: 500 ملغ، 5 ملغ/5 مل",
    )

    # ── Storage & control ─────────────────────────────────────────────────────
    requires_cold_chain = fields.Boolean(
        string="Cold Chain / سلسلة التبريد",
        default=False,
        help="Requires refrigeration (2–8 °C) / يتطلب التبريد (2–8 درجة مئوية)",
    )
    is_controlled = fields.Boolean(
        string="Controlled Substance / مادة مضبوطة",
        default=False,
        help="Narcotic / psychotropic substance requiring special record-keeping. / "
             "مادة مخدرة أو ذات تأثير نفسي تتطلب تسجيلاً خاصاً.",
    )
