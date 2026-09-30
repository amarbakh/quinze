# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
health.lab.request — Bridge Override (quinze_health_lab)
==========================================================
تجاوز الجسر في موديول المختبر

Inherits health.lab.request (defined in quinze_health_clinic) to:
  1. Add a FK to lab.order
  2. Override _action_create_lab_order() — the no-op hook in clinic —
     with the real creation logic.
  3. Add a smart button to open the linked lab order.

يرث health.lab.request المُعرَّف في موديول العيادة لـ:
  1. إضافة ربط FK بـ lab.order
  2. تجاوز الدالة _action_create_lab_order() بمنطق الإنشاء الحقيقي.
  3. إضافة زر ذكي لفتح أمر المختبر المرتبط.
"""

from odoo import api, fields, models


class HealthLabRequest(models.Model):
    _inherit = "health.lab.request"

    # ── FK to the created lab.order ───────────────────────────────────────────
    lab_order_id = fields.Many2one(
        comodel_name="lab.order",
        string="Lab Order / أمر المختبر",
        readonly=True,
        copy=False,
        ondelete="set null",
        tracking=True,
    )
    lab_order_state = fields.Selection(
        related="lab_order_id.state",
        string="Order State / حالة الأمر",
        readonly=True,
    )

    # ── Bridge hook override ──────────────────────────────────────────────────
    # Clinic and lab use different priority scales, so translate between them.
    # العيادة والمختبر يستخدمان مقاييس أولوية مختلفة، لذا نترجم بينهما.
    _LAB_PRIORITY_MAP = {
        "normal": "0",
        "urgent": "1",
        "stat": "2",
    }

    def _action_create_lab_order(self):
        """Override the clinic no-op: create a real lab.order.

        Called by health.lab.request.action_confirm() (in clinic module).
        Creates one lab.order per request and stores the FK.

        تجاوز الدالة الفارغة في العيادة: إنشاء lab.order حقيقي.
        يُستدعى عند تأكيد طلب المختبر من العيادة.
        يُنشئ أمر مختبر واحداً لكل طلب ويحفظ الربط.
        """
        for req in self:
            if req.lab_order_id:
                # Already created — skip (idempotent)
                continue
            order = self.env["lab.order"].create(
                {
                    "lab_request_id": req.id,
                    "patient_id": req.patient_id.id,
                    "doctor_id": req.doctor_id.id if req.doctor_id else False,
                    "order_date": req.request_date or fields.Date.context_today(req),
                    "priority": self._LAB_PRIORITY_MAP.get(req.priority, "0"),
                    "clinical_indication": req.clinical_indication or "",
                    "company_id": req.company_id.id
                    if req.company_id
                    else self.env.company.id,
                    "branch_id": req.branch_id.id if req.branch_id else False,
                }
            )
            req.lab_order_id = order
        return True

    # ── Smart button action ───────────────────────────────────────────────────
    def action_view_lab_order(self):
        """Open the linked lab.order form view.
        فتح نموذج أمر المختبر المرتبط.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "lab.order",
            "res_id": self.lab_order_id.id,
            "view_mode": "form",
            "target": "current",
        }
