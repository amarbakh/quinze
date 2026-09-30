# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
pharmacy.dispensing — Dispensing Record
=========================================
سجل الصرف الصيدلاني

Master record for a single dispensing transaction. Supports two modes:

  internal  — linked to a health.prescription from the clinic.
              Lines are pre-populated from the prescription.
              On dispense: updates prescription state (partially_dispensed /
              dispensed) and validates the stock.picking.

  external  — walk-in customer or patient with an external prescription.
              Pharmacist manually adds drug lines.
              On confirm: creates account.move (customer invoice).
              On dispense: validates picking + posts invoice.

State machine:
    draft → confirmed → dispensed / cancelled

دورة الحياة:
    مسودة → مؤكد → تم الصرف / ملغى
"""

from odoo import api, fields, models
from odoo.exceptions import UserError


class PharmacyDispensing(models.Model):
    _name = "pharmacy.dispensing"
    _description = "Pharmacy Dispensing / سجل صرف الصيدلية"
    _inherit = ["health.mixin"]
    _order = "dispensing_date desc, id desc"
    _rec_name = "dispensing_number"

    # ── Identity ──────────────────────────────────────────────────────────────
    dispensing_number = fields.Char(
        string="Dispensing No. / رقم الصرف",
        readonly=True,
        copy=False,
        default="New",
        index=True,
    )

    # ── Type ──────────────────────────────────────────────────────────────────
    dispensing_type = fields.Selection(
        selection=[
            ("internal", "Internal / داخلي (من وصفة العيادة)"),
            ("external", "External / خارجي (مريض خارجي)"),
        ],
        string="Dispensing Type / نوع الصرف",
        required=True,
        default="external",
        tracking=True,
    )

    # ── Links ─────────────────────────────────────────────────────────────────
    prescription_id = fields.Many2one(
        comodel_name="health.prescription",
        string="Prescription / الوصفة",
        ondelete="restrict",
        copy=False,
        tracking=True,
        domain="[('state','in',['confirmed','partially_dispensed'])]",
    )
    patient_id = fields.Many2one(
        comodel_name="health.patient",
        string="Patient / المريض",
        ondelete="restrict",
        tracking=True,
        index=True,   # perf: searched in reports and portal
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Customer / العميل",
        tracking=True,
        index=True,
        help="Used for external dispensing invoicing / للفوترة في الصرف الخارجي",
    )
    pharmacist_id = fields.Many2one(
        comodel_name="res.users",
        string="Pharmacist / الصيدلاني",
        default=lambda self: self.env.uid,
        tracking=True,
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    dispensing_date = fields.Date(
        string="Date / التاريخ",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    dispensed_at = fields.Datetime(
        string="Dispensed At / وقت الصرف",
        readonly=True,
        copy=False,
    )

    # ── Lines ─────────────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        comodel_name="pharmacy.dispensing.line",
        inverse_name="dispensing_id",
        string="Medications / الأدوية",
    )

    # ── Stock ─────────────────────────────────────────────────────────────────
    picking_id = fields.Many2one(
        comodel_name="stock.picking",
        string="Stock Picking / حركة المخزون",
        readonly=True,
        copy=False,
    )
    picking_state = fields.Selection(
        related="picking_id.state",
        string="Picking State",
        readonly=True,
    )

    # ── Invoice (external) ────────────────────────────────────────────────────
    invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice / الفاتورة",
        readonly=True,
        copy=False,
    )
    invoice_state = fields.Selection(
        related="invoice_id.state",
        string="Invoice State",
        readonly=True,
    )

    # ── Insurance ─────────────────────────────────────────────────────────────
    insurance_claim_ids = fields.One2many(
        comodel_name="pharmacy.insurance.claim",
        inverse_name="dispensing_id",
        string="Insurance Claims / مطالبات التأمين",
    )
    insurance_claim_count = fields.Integer(
        compute="_compute_insurance_claim_count",
        string="# Claims",
    )

    # ── Amounts ───────────────────────────────────────────────────────────────
    amount_total = fields.Monetary(
        string="Total / المجموع",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        readonly=True,
    )

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ("draft", "Draft / مسودة"),
            ("confirmed", "Confirmed / مؤكد"),
            ("dispensed", "Dispensed / تم الصرف"),
            ("cancelled", "Cancelled / ملغى"),
        ],
        string="State / الحالة",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
        index=True,   # perf: filtered heavily in views and API
    )

    # ── Notes ─────────────────────────────────────────────────────────────────
    note = fields.Text(string="Notes / ملاحظات")

    # ── SQL Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        (
            "dispensing_number_company_uniq",
            "UNIQUE(dispensing_number, company_id)",
            "Dispensing number must be unique per company / رقم الصرف يجب أن يكون فريداً لكل شركة",
        ),
    ]

    # ── Sequence ──────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        """Assign dispensing_number from sequence on creation.
        تعيين رقم الصرف من التسلسل عند الإنشاء.
        """
        for vals in vals_list:
            if vals.get("dispensing_number", "New") == "New":
                vals["dispensing_number"] = (
                    self.env["ir.sequence"].next_by_code("pharmacy.dispensing")
                    or "DIS/000001"
                )
        return super().create(vals_list)

    # ── Onchange: populate from prescription ──────────────────────────────────
    @api.onchange("prescription_id")
    def _onchange_prescription_id(self):
        """Auto-fill patient and lines from the linked prescription.
        تعبئة تلقائية للمريض والأسطر من الوصفة المحددة.
        """
        if not self.prescription_id:
            return
        rx = self.prescription_id
        self.patient_id = rx.patient_id
        # Keep partner strictly aligned with the prescription's patient so a
        # stale/default partner (e.g. the company itself) is never carried over.
        self.partner_id = rx.patient_id.partner_id or False
        # Clear existing lines and rebuild from prescription
        self.line_ids = [(5, 0, 0)]
        new_lines = []
        for rx_line in rx.prescription_line_ids:
            remaining = rx_line.qty_to_dispense - rx_line.dispensed_qty
            if remaining > 0:
                new_lines.append(
                    (
                        0,
                        0,
                        {
                            "product_id": rx_line.product_id.id,
                            "prescription_line_id": rx_line.id,
                            "qty_ordered": rx_line.qty_to_dispense,
                            "qty_dispensed": remaining,
                            "price_unit": rx_line.product_id.lst_price,
                            "lot_id": False,
                        },
                    )
                )
        self.line_ids = new_lines

    # ── Computes ──────────────────────────────────────────────────────────────
    @api.depends("line_ids.subtotal")
    def _compute_amounts(self) -> None:
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped("subtotal"))

    def _compute_insurance_claim_count(self) -> None:
        for rec in self:
            rec.insurance_claim_count = len(rec.insurance_claim_ids)

    # ── State actions ─────────────────────────────────────────────────────────
    def action_confirm(self):
        """Confirm dispensing: validate lines, create stock.picking,
        and (for external) create account.move.

        تأكيد الصرف: التحقق من الأسطر، إنشاء stock.picking،
        وإنشاء الفاتورة للصرف الخارجي.
        """
        for rec in self.filtered(lambda d: d.state == "draft"):
            if not rec.line_ids:
                raise UserError(
                    "Please add at least one medication line before confirming. / "
                    "الرجاء إضافة دواء واحد على الأقل قبل التأكيد."
                )

            # Tracked medications must carry a lot, otherwise stock validation
            # fails later with a generic message.
            # الأدوية المتتبعة بالتشغيلة يجب أن تحمل رقم تشغيلة.
            missing_lot = rec.line_ids.filtered(
                lambda l: l.qty_dispensed > 0
                and l.product_id.tracking != "none"
                and not l.lot_id
            )
            if missing_lot:
                names = "\n".join(
                    "- %s" % l.product_id.display_name for l in missing_lot
                )
                raise UserError(
                    "A Lot/Serial Number is required for: / "
                    "رقم التشغيلة مطلوب للأدوية التالية:\n%s" % names
                )

            rec._create_stock_picking()
            if rec.dispensing_type == "external":
                rec._create_invoice()
            rec.state = "confirmed"

    def action_dispense(self):
        """Complete the dispensing: validate stock picking,
        update prescription state (internal), post invoice (external).

        إتمام الصرف: تأكيد حركة المخزون،
        تحديث حالة الوصفة (داخلي)، ترحيل الفاتورة (خارجي).
        """
        for rec in self.filtered(lambda d: d.state == "confirmed"):
            # Validate stock picking
            if rec.picking_id and rec.picking_id.state not in (
                "done",
                "cancel",
            ):
                rec._validate_picking()
            rec.write(
                {
                    "state": "dispensed",
                    "dispensed_at": fields.Datetime.now(),
                }
            )
            # Update prescription for internal dispensing
            if rec.dispensing_type == "internal" and rec.prescription_id:
                rec._update_prescription_state()
            # Post invoice for external dispensing
            if rec.dispensing_type == "external" and rec.invoice_id:
                if rec.invoice_id.state == "draft":
                    rec.invoice_id.action_post()

    def action_cancel(self):
        """Cancel the dispensing and revert related documents.
        إلغاء الصرف وإعادة المستندات المرتبطة.
        """
        for rec in self.filtered(lambda d: d.state in ("draft", "confirmed")):
            if rec.picking_id and rec.picking_id.state not in (
                "done",
                "cancel",
            ):
                rec.picking_id.action_cancel()
            if rec.invoice_id and rec.invoice_id.state == "draft":
                rec.invoice_id.button_cancel()
            rec.state = "cancelled"

    def action_reset_draft(self):
        """Reset cancelled dispensing to draft.
        إعادة الصرف الملغى للمسودة.
        """
        for rec in self.filtered(lambda d: d.state == "cancelled"):
            rec.state = "draft"

    def action_print_receipt(self):
        """Print dispensing receipt / طباعة إيصال الصرف."""
        self.ensure_one()
        return self.env.ref(
            "quinze_health_pharmacy.action_report_dispensing_receipt"
        ).report_action(self)

    def action_view_invoice(self):
        """Open the linked invoice / فتح الفاتورة."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.invoice_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_picking(self):
        """Open the linked stock picking / فتح حركة المخزون."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.picking_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_create_insurance_claim(self):
        """Create an insurance claim for this dispensing.
        إنشاء مطالبة تأمينية لهذا الصرف.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "pharmacy.insurance.claim",
            "view_mode": "form",
            "context": {
                "default_dispensing_id": self.id,
                "default_patient_id": self.patient_id.id,
                "default_amount_claimed": self.amount_total,
            },
            "target": "new",
        }

    # ── Private helpers ───────────────────────────────────────────────────────
    def _get_pharmacy_location(self):
        """Return the pharmacy stock.location (virtual or real).
        إرجاع موقع المخزون للصيدلية.
        """
        location = self.env.ref(
            "quinze_health_pharmacy.stock_location_pharmacy", raise_if_not_found=False
        )
        if not location:
            # Fallback: use WH/Stock
            location = self.env["stock.warehouse"].search(
                [("company_id", "=", self.company_id.id)], limit=1
            ).lot_stock_id
        return location

    def _get_customer_location(self):
        """Return the virtual 'Customers' location.
        إرجاع موقع العملاء الافتراضي.
        """
        return self.env.ref("stock.stock_location_customers")

    def _get_pharmacy_picking_type(self):
        """Return (or create) the pharmacy OUT operation type.
        إرجاع نوع عملية الإخراج للصيدلية.
        """
        ptype = self.env.ref(
            "quinze_health_pharmacy.picking_type_pharmacy_out",
            raise_if_not_found=False,
        )
        if not ptype:
            warehouse = self.env["stock.warehouse"].search(
                [("company_id", "=", self.company_id.id)], limit=1
            )
            ptype = warehouse.out_type_id
        return ptype

    def _create_stock_picking(self):
        """Create a stock.picking for each dispensing.
        إنشاء stock.picking لكل صرف.
        """
        self.ensure_one()
        src_location = self._get_pharmacy_location()
        dest_location = self._get_customer_location()
        picking_type = self._get_pharmacy_picking_type()

        partner = self.partner_id or (
            self.patient_id.partner_id if self.patient_id else False
        )

        picking = self.env["stock.picking"].create(
            {
                "partner_id": partner.id if partner else False,
                "picking_type_id": picking_type.id,
                "location_id": src_location.id,
                "location_dest_id": dest_location.id,
                "origin": self.dispensing_number,
                "company_id": self.company_id.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": line.product_id.name,
                            "product_id": line.product_id.id,
                            "product_uom": line.product_id.uom_id.id,
                            "product_uom_qty": line.qty_dispensed,
                            "location_id": src_location.id,
                            "location_dest_id": dest_location.id,
                        },
                    )
                    for line in self.line_ids
                    if line.product_id and line.qty_dispensed > 0
                ],
            }
        )
        self.picking_id = picking

    def _validate_picking(self):
        """Immediately validate the picking (set all done quantities).
        تأكيد حركة المخزون فوراً بتعيين الكميات المنجزة.
        """
        self.ensure_one()
        picking = self.picking_id
        if picking.state == "draft":
            picking.action_confirm()
        if picking.state in ("confirmed", "waiting", "assigned"):
            picking.action_assign()

        # Assign the lot chosen on each dispensing line to its stock move line,
        # then set done qty = demanded qty.
        # ربط رقم التشغيلة المختار في سطر الصرف بسطر حركة المخزون.
        for move in picking.move_ids:
            disp_line = self.line_ids.filtered(
                lambda l, m=move: l.product_id == m.product_id
                and l.qty_dispensed > 0
            )[:1]
            tracking = move.product_id.tracking

            if tracking != "none" and disp_line and disp_line.lot_id:
                # Reservation may have produced several move lines; keep one.
                if len(move.move_line_ids) > 1:
                    move.move_line_ids[1:].unlink()
                if not move.move_line_ids:
                    self.env["stock.move.line"].create(
                        {
                            "move_id": move.id,
                            "picking_id": picking.id,
                            "product_id": move.product_id.id,
                            "product_uom_id": move.product_uom.id,
                            "location_id": move.location_id.id,
                            "location_dest_id": move.location_dest_id.id,
                        }
                    )
                move.move_line_ids.lot_id = disp_line.lot_id
                move.move_line_ids.quantity = move.product_uom_qty
            else:
                move.quantity = move.product_uom_qty

        picking.button_validate()

    def _create_invoice(self):
        """Create a draft customer invoice for external dispensing.
        إنشاء فاتورة عميل مسودة للصرف الخارجي.
        """
        self.ensure_one()
        partner = self.partner_id or (
            self.patient_id.partner_id if self.patient_id else False
        )
        if not partner:
            raise UserError(
                "Please select a customer or patient for external dispensing invoicing. / "
                "الرجاء تحديد عميل أو مريض لفوترة الصرف الخارجي."
            )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": self.dispensing_date,
                "invoice_origin": self.dispensing_number,
                "company_id": self.company_id.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": line.product_id.id,
                            "name": line.product_id.name,
                            "quantity": line.qty_dispensed,
                            "price_unit": line.price_unit,
                            "tax_ids": [
                                (6, 0, line.product_id.taxes_id.ids)
                            ],
                        },
                    )
                    for line in self.line_ids
                    if line.product_id and line.qty_dispensed > 0
                ],
            }
        )
        self.invoice_id = invoice

    def _update_prescription_state(self):
        """Update prescription and prescription lines after internal dispensing.
        تحديث حالة الوصفة وبنودها بعد الصرف الداخلي.
        """
        self.ensure_one()
        rx = self.prescription_id
        if not rx:
            return
        # Update dispensed_qty on each prescription line
        for disp_line in self.line_ids:
            if disp_line.prescription_line_id:
                rx_line = disp_line.prescription_line_id
                rx_line.dispensed_qty = (
                    rx_line.dispensed_qty + disp_line.qty_dispensed
                )
        # Recompute prescription state
        rx._compute_dispensing_state()
