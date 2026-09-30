# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
quinze.api.key — API Key Management
=====================================
إدارة مفاتيح واجهة برمجة التطبيقات

Each key is linked to a res.user and carries:
  - a random 64-char hex token (generated on create)
  - an optional IP whitelist
  - an expiry date
  - a scopes list (read / write)

كل مفتاح مرتبط بمستخدم Odoo ويحمل:
  - رمزاً عشوائياً 64 حرف
  - قائمة بيضاء للـ IP (اختياري)
  - تاريخ انتهاء
  - نطاق الصلاحية (قراءة / كتابة)
"""
import secrets

from odoo import api, fields, models
from odoo.exceptions import UserError


class QuinzeApiKey(models.Model):
    _name = "quinze.api.key"
    _description = "QUINZE API Key / مفتاح API"
    _order = "create_date desc"
    _rec_name = "name"

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string="Key Name / اسم المفتاح",
        required=True,
        help="Descriptive label for this key (e.g. 'Mobile App v2'). / "
             "وصف للمفتاح مثل: تطبيق الجوال الإصدار 2.",
    )
    token = fields.Char(
        string="Token / الرمز",
        readonly=True,
        copy=False,
        index=True,
        help="64-character hex token. Shown only once on creation. / "
             "رمز 64 حرفاً. يُعرض مرة واحدة فقط عند الإنشاء.",
    )
    token_preview = fields.Char(
        string="Token Preview / معاينة الرمز",
        compute="_compute_token_preview",
        help="First 8 characters for identification. / "
             "أول 8 أحرف للتعرف على المفتاح.",
    )

    # ── Ownership ─────────────────────────────────────────────────────────────
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User / المستخدم",
        required=True,
        ondelete="cascade",
        default=lambda self: self.env.uid,
        help="API calls will run as this user. / "
             "طلبات الـ API تُنفَّذ بصلاحيات هذا المستخدم.",
    )

    # ── Access control ────────────────────────────────────────────────────────
    scope = fields.Selection(
        selection=[
            ("read", "Read Only / قراءة فقط"),
            ("write", "Read & Write / قراءة وكتابة"),
        ],
        string="Scope / النطاق",
        required=True,
        default="read",
    )
    ip_whitelist = fields.Text(
        string="IP Whitelist / قائمة IP المسموح بها",
        help="One IP per line. Leave empty to allow all. / "
             "IP واحد في كل سطر. اتركه فارغاً للسماح بالجميع.",
    )

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    expiry_date = fields.Date(
        string="Expiry Date / تاريخ الانتهاء",
        help="Leave empty for no expiry. / اتركه فارغاً لعدم الانتهاء.",
    )
    active = fields.Boolean(default=True)
    last_used = fields.Datetime(
        string="Last Used / آخر استخدام",
        readonly=True,
        copy=False,
    )
    request_count = fields.Integer(
        string="# Requests / عدد الطلبات",
        readonly=True,
        copy=False,
        default=0,
    )

    # ── Compute ───────────────────────────────────────────────────────────────
    @api.depends("token")
    def _compute_token_preview(self) -> None:
        for rec in self:
            rec.token_preview = (rec.token[:8] + "…") if rec.token else ""

    # ── Constraints ───────────────────────────────────────────────────────────
    _sql_constraints = [
        ("token_unique", "UNIQUE(token)", "API token must be unique / الرمز يجب أن يكون فريداً"),
    ]

    # ── Create: auto-generate token ──────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        """Auto-generate a cryptographically secure token on creation.
        توليد رمز آمن تلقائياً عند الإنشاء.
        """
        for vals in vals_list:
            if not vals.get("token"):
                vals["token"] = secrets.token_hex(32)   # 64-char hex
        return super().create(vals_list)

    # ── Public API ────────────────────────────────────────────────────────────
    @api.model
    def authenticate(self, token: str, ip: str | None = None) -> "QuinzeApiKey | None":
        """Return the API key record if token is valid, active, and not expired.
        Returns None if invalid.

        يُرجع سجل المفتاح إذا كان صالحاً ونشطاً وغير منتهٍ.
        يُرجع None إذا كان غير صالح.
        """
        if not token:
            return None
        key = self.sudo().search([("token", "=", token), ("active", "=", True)], limit=1)
        if not key:
            return None
        # Check expiry
        if key.expiry_date and key.expiry_date < fields.Date.today():
            return None
        # Check IP whitelist
        if ip and key.ip_whitelist:
            allowed = [line.strip() for line in key.ip_whitelist.splitlines() if line.strip()]
            if allowed and ip not in allowed:
                return None
        # Update usage stats (sudo to avoid ACL issues on this lightweight write)
        key.sudo().write({
            "last_used": fields.Datetime.now(),
            "request_count": key.request_count + 1,
        })
        return key

    def action_rotate(self):
        """Generate a new token, invalidating the old one.
        توليد رمز جديد وإبطال القديم.
        """
        self.ensure_one()
        self.token = secrets.token_hex(32)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Token Rotated / تم تجديد الرمز",
                "message": f"New token: {self.token}",
                "type": "warning",
                "sticky": True,
            },
        }

    def action_revoke(self):
        """Deactivate this key immediately / تعطيل المفتاح فوراً."""
        self.active = False
