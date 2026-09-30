# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
lab.test.category — Laboratory Test Category
==============================================
تصنيف الفحوصات المخبرية

Stores top-level groupings for lab tests, e.g.
Hematology / الدم الكامل, Biochemistry / الكيمياء الحيوية.
"""

from odoo import fields, models


class LabTestCategory(models.Model):
    _name = "lab.test.category"
    _description = "Lab Test Category / تصنيف الفحوصات المخبرية"
    _inherit = ["mail.thread"]
    _order = "sequence, name"

    # ── Identity ────────────────────────────────────────────────────────────
    name = fields.Char(
        string="Category Name",
        required=True,
        translate=True,
        tracking=True,
    )
    name_ar = fields.Char(
        string="Arabic Name / الاسم بالعربية",
        translate=False,
        tracking=True,
    )
    code = fields.Char(
        string="Code / الرمز",
        size=10,
        required=True,
        copy=False,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )
    color = fields.Integer(
        string="Color",
        default=0,
    )
    active = fields.Boolean(
        string="Active / نشط",
        default=True,
        tracking=True,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    test_ids = fields.One2many(
        comodel_name="lab.test",
        inverse_name="category_id",
        string="Tests / الفحوصات",
    )
    test_count = fields.Integer(
        string="# Tests",
        compute="_compute_test_count",
        store=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company / الشركة",
        default=lambda self: self.env.company,
        required=True,
    )

    # ── SQL constraints ──────────────────────────────────────────────────────
    _sql_constraints = [
        (
            "code_company_uniq",
            "UNIQUE(code, company_id)",
            "Category code must be unique per company / رمز التصنيف يجب أن يكون فريداً.",
        )
    ]

    # ── Computes ─────────────────────────────────────────────────────────────
    def _compute_test_count(self) -> None:
        """Count the number of tests per category.
        حساب عدد الفحوصات لكل تصنيف.
        """
        for rec in self:
            rec.test_count = len(rec.test_ids)

    def action_view_tests(self) -> dict:
        """Open the list of lab tests belonging to this category.

        فتح قائمة الفحوصات المخبرية لهذا التصنيف.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tests / الفحوصات',
            'res_model': 'lab.test',
            'view_mode': 'tree,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id},
        }

