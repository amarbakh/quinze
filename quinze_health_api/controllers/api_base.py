# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
api_base.py — Base Controller & Helpers
=========================================
المتحكم الأساسي والدوال المساعدة

Provides:
  - QuinzeApiBase.dispatch()  — authentication gate for every endpoint
  - ok()      — build a success JSON response
  - err()     — build an error JSON response
  - paginate()— extract ?page= and ?limit= from the query string
  - _serialize_record() — convert an ORM record to a plain dict

يوفر:
  - بوابة المصادقة لجميع نقاط النهاية
  - بناء استجابات JSON موحدة (نجاح / خطأ)
  - الترقيم الصفحي
  - تحويل سجلات ORM إلى قواميس JSON
"""

import json
import logging

from odoo import http
from odoo.http import Response, request

_logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
API_PREFIX = "/api/quinze/v1"
PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100


# ── Response helpers ───────────────────────────────────────────────────────────

def ok(data, *, total: int = None, page: int = 1, limit: int = PAGE_SIZE_DEFAULT) -> Response:
    """Return a 200 JSON success envelope.

    يُرجع استجابة JSON ناجحة بالغلاف الموحد.

    ::

        {"status": "ok", "data": ..., "meta": {"total": n, "page": p, "limit": l}}
    """
    payload = {"status": "ok", "data": data}
    if total is not None:
        payload["meta"] = {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": max(1, -(-total // limit)),   # ceiling division
        }
    return Response(
        json.dumps(payload, ensure_ascii=False, default=str),
        status=200,
        content_type="application/json; charset=utf-8",
    )


def err(message: str, code: int = 400, *, detail: str = "") -> Response:
    """Return an error JSON envelope.

    يُرجع غلاف JSON لرسالة الخطأ.

    ::

        {"status": "error", "code": 400, "message": "...", "detail": "..."}
    """
    payload = {"status": "error", "code": code, "message": message}
    if detail:
        payload["detail"] = detail
    return Response(
        json.dumps(payload, ensure_ascii=False),
        status=code,
        content_type="application/json; charset=utf-8",
    )


# ── Pagination helper ──────────────────────────────────────────────────────────

def paginate() -> tuple[int, int, int]:
    """Extract pagination params from the current request.
    استخراج معاملات الترقيم من الطلب الحالي.

    Returns (offset, limit, page).
    """
    try:
        page = max(1, int(request.params.get("page", 1)))
        limit = min(PAGE_SIZE_MAX, max(1, int(request.params.get("limit", PAGE_SIZE_DEFAULT))))
    except (ValueError, TypeError):
        page, limit = 1, PAGE_SIZE_DEFAULT
    offset = (page - 1) * limit
    return offset, limit, page


# ── ORM → dict serializer ─────────────────────────────────────────────────────

def _m2o(field_value) -> dict | None:
    """Serialize a Many2one field value to {id, name}.
    تحويل حقل Many2one إلى {id, name}.
    """
    if not field_value:
        return None
    return {"id": field_value.id, "name": field_value.display_name or field_value.name}


def _date(d) -> str | None:
    """Convert a date/datetime to ISO string.
    تحويل التاريخ إلى نص ISO.
    """
    return d.isoformat() if d else None


# ── Base controller ────────────────────────────────────────────────────────────

class QuinzeApiBase(http.Controller):
    """Base class providing the authentication gate and shared utilities.
    الفئة الأساسية التي توفر بوابة المصادقة والأدوات المشتركة.

    Subclasses call ``self._auth()`` at the start of every route handler.
    The returned ``(env, key)`` tuple gives:
      * ``env`` — ORM environment scoped to the API user
      * ``key`` — the authenticated quinze.api.key record

    الفئات الفرعية تستدعي ``self._auth()`` في بداية كل دالة معالجة.
    """

    def _auth(self) -> tuple:
        """Authenticate the request via X-API-Key header.
        مصادقة الطلب عبر ترويسة X-API-Key.

        Returns (env, api_key) on success.
        Raises an HTTP 401 Response on failure — callers must return it.

        يُرجع (env, api_key) عند النجاح.
        يُرجع Response 401 عند الفشل.
        """
        token = request.httprequest.headers.get("X-API-Key", "").strip()
        ip = request.httprequest.remote_addr

        key = request.env["quinze.api.key"].authenticate(token, ip)
        if not key:
            raise _AuthError()

        # Build an env scoped to the API user (respects their access rights)
        env = request.env(user=key.user_id.id)
        return env, key

    def _require_write(self, key) -> None:
        """Raise _AuthError if the key is read-only.
        يرفع خطأ إذا كان المفتاح للقراءة فقط.
        """
        if key.scope == "read":
            raise _PermError("This API key is read-only. / هذا المفتاح للقراءة فقط.")


class _AuthError(Exception):
    """Raised when authentication fails / فشل المصادقة."""


class _PermError(Exception):
    """Raised when scope is insufficient / النطاق غير كافٍ."""


# ── Decorator-level auth wrapper ──────────────────────────────────────────────

def api_route(route, methods=None, auth_required=True, write_required=False):
    """Decorator factory for QUINZE API routes.
    مُزخرف لمسارات QUINZE API.

    Handles auth, JSON parsing, and uniform error catching so individual
    handlers can focus on business logic.

    يعالج المصادقة وتحليل JSON والأخطاء بشكل موحد.
    """
    if methods is None:
        methods = ["GET"]

    def decorator(func):
        @http.route(
            f"{API_PREFIX}{route}",
            type="http",
            auth="none",       # We handle auth ourselves via X-API-Key
            methods=methods,
            csrf=False,        # APIs don't use CSRF tokens
            cors="*",
        )
        def wrapper(self, *args, **kwargs):
            # ── Authentication ────────────────────────────────────────────
            if auth_required:
                try:
                    env, key = self._auth()
                except _AuthError:
                    return err("Unauthorized. Provide a valid X-API-Key header. / "
                               "غير مصرح. يُرجى تقديم مفتاح X-API-Key صالح.", 401)
                except _PermError as e:
                    return err(str(e), 403)

                if write_required:
                    try:
                        self._require_write(key)
                    except _PermError as e:
                        return err(str(e), 403)
            else:
                env = request.env
                key = None

            # ── Parse JSON body for POST/PUT/PATCH ───────────────────────
            body = {}
            if request.httprequest.method in ("POST", "PUT", "PATCH"):
                try:
                    raw = request.httprequest.data
                    if raw:
                        body = json.loads(raw.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    return err(f"Invalid JSON body: {exc}", 400)

            # ── Delegate to handler ───────────────────────────────────────
            try:
                return func(self, env, key, body, *args, **kwargs)
            except _PermError as e:
                return err(str(e), 403)
            except Exception as exc:   # noqa: BLE001
                _logger.exception("QUINZE API unhandled error in %s", func.__name__)
                return err(
                    "Internal server error. / خطأ داخلي في الخادم.",
                    500,
                    detail=str(exc),
                )

        wrapper.__name__ = func.__name__
        return wrapper

    return decorator
