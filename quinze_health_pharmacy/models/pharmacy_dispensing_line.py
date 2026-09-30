# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
pharmacy.dispensing.line — Dispensing Line
============================================
بند الصرف الصيدلاني

One line per medication in a dispensing transaction.
For internal dispensing: linked back to a health.prescription.line.

سطر واحد لكل دواء في عملية الصرف.
للصرف الداخلي: مرتبط بسطر الوصفة الطبية.
"""

from odoo import api, fields, models


class PharmacyDispensingLine(models.Model):
    _name = "pharmacy.dispensing.line"
    _description = "Dispensing Line / بند صرف"
    _order = "sequence, id"

    # ── Parent ────────────────────────────────────────────────────────────────
    dispensing_id = fields.Many2one(
        comodel_name="pharmacy.dispensing",
        string="Dispensing / الصرف",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)

    # ── Prescription link (internal dispensing) ───────────────────────────────
    prescription_line_id = fields.Many2one(
        comodel_name="health.prescription.line",
        string="Rx Line / سطر الوصفة",
        ondelete="set null",
        copy=False,
    )

    # ── Product ───────────────────────────────────────────────────────────────
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Medication / الدواء",
        required=True,
        domain="[('is_medication','=',True)]",
        ondelete="restrict",
    )
    drug_name_ar = fields.Char(
        string="Drug Name (AR) / اسم الدواء",
        compute="_compute_drug_name_ar",
        store=True,
    )

    # ── Quantities ────────────────────────────────────────────────────────────
    qty_ordered = fields.Float(
        string="Ordered / المطلوب",
        digits=(10, 2),
        default=0.0,
        help="Quantity from the prescription / الكمية من الوصفة",
    )
    qty_dispensed = fields.Float(
        string="Dispensed / المصروف",
        digits=(10, 2),
        default=1.0,
        required=True,
    )
    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit / الوحدة",
        compute="_compute_uom",
        store=True,
    )

    # ── Stock (lot/serial/expiry) ─────────────────────────────────────────────
    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Batch / Lot",
        domain="[('product_id','=',product_id)]",
        help="Batch number / lot for expiry tracking",
    )
    expiry_date = fields.Date(
        string="Expiry / انتهاء الصلاحية",
        help=(
            "Expiry date for this batch/lot.\n"
            "تاريخ انتهاء صلاحية هذه الدفعة."
        ),
    )

    # ── Pricing ───────────────────────────────────────────────────────────────
    price_unit = fields.Float(
        string="Unit Price / سعر الوحدة",
        digits="Product Price",
        default=0.0,
    )
    subtotal = fields.Monetary(
        string="Subtotal / المجموع الفرعي",
        compute="_compute_subtotal",
        store=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="dispensing_id.currency_id",
        readonly=True,
    )

    # ── Patient instructions / substitution ──────────────────────────────────
    instructions = fields.Text(
        string="Instructions / التعليمات",
    )
    is_substitution = fields.Boolean(
        string="Substitution / بديل",
        default=False,
        help="True if this is a generic substitution for the prescribed brand / "
             "صحيح إذا كان هذا بديلاً جنيسياً للعلامة التجارية المكتوبة في الوصفة.",
    )

    # ── Computes ──────────────────────────────────────────────────────────────
    @api.depends("product_id")
    def _compute_drug_name_ar(self) -> None:
        for line in self:
            tmpl = line.product_id.product_tmpl_id
            line.drug_name_ar = (
                getattr(tmpl, "generic_name_ar", None) or ""
            )

    @api.depends("product_id")
    def _compute_uom(self) -> None:
        for line in self:
            line.uom_id = line.product_id.uom_id if line.product_id else False

    @api.depends("qty_dispensed", "price_unit")
    def _compute_subtotal(self) -> None:
        for line in self:
            line.subtotal = line.qty_dispensed * line.price_unit

    # ── Onchange ─────────────────────────────────────────────────────────────
    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.lst_price
            # Inherit instructions from prescription line if available
            if self.prescription_line_id:
                self.instructions = self.prescription_line_id.instructions
        # A lot belongs to a single product, so clear it when the drug changes.
        # رقم التشغيلة مرتبط بدواء واحد، لذا يُمسح عند تغيير الدواء.
        self.lot_id = False
        self.expiry_date = False

    @api.onchange("lot_id")
    def _onchange_lot_id(self):
        """Pull the expiry date from the selected lot.

        جلب تاريخ انتهاء الصلاحية من التشغيلة المختارة.
        """
        if not self.lot_id:
            self.expiry_date = False
            return
        # Odoo stores it as a Datetime on stock.lot; the line field is a Date.
        expiration = self.lot_id.expiration_date
        self.expiry_date = expiration.date() if expiration else False
