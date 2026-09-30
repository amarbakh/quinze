# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
pharmacy.drug.category — Drug Classification
=============================================
تصنيف الأدوية

Therapeutic/pharmacological categories used to classify medications.
e.g. Analgesics / Antibiotics / Antihypertensives ...

الفئات العلاجية/الصيدلانية المستخدمة لتصنيف الأدوية.
مثال: مسكنات الألم / مضادات حيوية / خافضات الضغط ...
"""

from odoo import fields, models, api


class PharmacyDrugCategory(models.Model):
    _name = "pharmacy.drug.category"
    _description = "Drug Category / تصنيف دواء"
    _order = "name"

    name = fields.Char(
        string="Category Name",
        required=True,
        translate=True,
    )
    name_ar = fields.Char(
        string="Arabic Name / الاسم بالعربية",
    )
    code = fields.Char(
        string="Code / الرمز",
        size=10,
    )
    description = fields.Text(
        string="Description / الوصف",
        translate=True,
    )
    active = fields.Boolean(default=True)
    product_count = fields.Integer(
        string="# Medications",
        compute="_compute_product_count",
    )

    def _compute_product_count(self) -> None:
        """Count active medication products in this category.
        عدد المنتجات الدوائية النشطة في هذا التصنيف.
        """
        for rec in self:
            rec.product_count = self.env["product.template"].with_context(
                active_test=False
            ).search_count([
                ("drug_category_id", "=", rec.id),
                ("is_medication", "=", True),
                ("active", "=", True),
            ])

    # ── Smart button action ───────────────────────────────────────────────────
    def action_view_medications(self):
        """Open the list of medications in this category.
        فتح قائمة الأدوية المنتمية لهذا التصنيف.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Medications — {self.name}",
            "res_model": "product.template",
            "view_mode": "tree,form",
            "domain": [
                ("drug_category_id", "=", self.id),
                ("is_medication", "=", True),
            ],
            "context": {
                "default_drug_category_id": self.id,
                "default_is_medication": True,
            },
        }
