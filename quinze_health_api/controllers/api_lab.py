# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
api_lab.py — Lab REST Endpoints
=================================
نقاط نهاية REST للمختبر

Routes (prefix: /api/quinze/v1):
  GET  /lab/orders              — list lab orders (filters: state, patient_id)
  GET  /lab/orders/<id>         — order detail with all results
  POST /lab/orders/<id>/result  — submit a single test result
  GET  /lab/tests               — catalog of available lab tests
"""

from odoo.http import request

from .api_base import (
    QuinzeApiBase,
    _date,
    _m2o,
    api_route,
    err,
    ok,
    paginate,
)


# ── Serializers ────────────────────────────────────────────────────────────────

def _lab_order(order, detail=False) -> dict:
    """Serialize lab.order to dict.
    تحويل lab.order إلى قاموس.
    """
    data = {
        "id": order.id,
        "number": order.order_number,
        "patient": _m2o(order.patient_id),
        "doctor": _m2o(order.doctor_id),
        "order_date": _date(order.order_date),
        "state": order.state,
        "line_count": order.line_count,
        "result_count": order.result_count,
        "abnormal_count": order.abnormal_count,
        "critical_count": order.critical_count,
        "sample_count": order.sample_count,
    }
    if detail:
        # Samples
        data["samples"] = [
            {
                "id": s.id,
                "number": s.sample_number,
                "type": s.sample_type,
                "state": s.state,
                "collected_at": _date(s.collection_datetime),
                "received_at": _date(s.received_datetime),
            }
            for s in order.sample_ids
        ]
        # Results
        data["results"] = [
            {
                "id": ln.id,
                "test": {
                    "id": ln.test_id.id,
                    "code": ln.test_id.code,
                    "name": ln.test_id.name,
                    "name_ar": ln.test_id.name_ar or "",
                    "unit": ln.test_id.unit or "",
                    "result_type": ln.test_id.result_type,
                },
                "result_value": ln.result_value,
                "result_text": ln.result_text or "",
                "result_bool": ln.result_bool,
                "ref_display": ln.ref_display or "",
                "flag": ln.flag,
                "state": ln.state,
                "resulted_at": _date(ln.resulted_at),
                "resulted_by": _m2o(ln.resulted_by_id),
            }
            for ln in order.line_ids
        ]
    return data


def _lab_test(test) -> dict:
    """Serialize lab.test catalog entry.
    تحويل lab.test إلى قاموس.
    """
    return {
        "id": test.id,
        "code": test.code,
        "name": test.name,
        "name_ar": test.name_ar or "",
        "category": _m2o(test.category_id),
        "result_type": test.result_type,
        "unit": test.unit or "",
        "sample_type": test.sample_type,
        "ref_low": test.ref_low,
        "ref_high": test.ref_high,
        "ref_low_male": test.ref_low_male,
        "ref_high_male": test.ref_high_male,
        "ref_low_female": test.ref_low_female,
        "ref_high_female": test.ref_high_female,
        "critical_low": test.critical_low,
        "critical_high": test.critical_high,
        "active": test.active,
    }


# ── Controller ─────────────────────────────────────────────────────────────────

class LabApiController(QuinzeApiBase):
    """REST endpoints for the Lab module.
    نقاط نهاية REST لوحدة المختبر.
    """

    # ── Lab Orders ─────────────────────────────────────────────────────────────

    @api_route("/lab/orders", methods=["GET"])
    def list_lab_orders(self, env, key, body):
        """GET /api/quinze/v1/lab/orders
        List lab orders with optional filters.
        قائمة طلبات المختبر مع فلاتر اختيارية.

        Query params:
          ?state=draft|sample_collected|in_progress|done|cancelled
          ?patient_id=<id>
          ?date_from=YYYY-MM-DD
          ?date_to=YYYY-MM-DD
          ?page=1&limit=20
        """
        domain = []
        params = request.params
        if params.get("state"):
            domain.append(("state", "=", params["state"]))
        if params.get("patient_id"):
            try:
                domain.append(("patient_id", "=", int(params["patient_id"])))
            except ValueError:
                return err("Invalid patient_id.", 400)
        if params.get("date_from"):
            domain.append(("order_date", ">=", params["date_from"]))
        if params.get("date_to"):
            domain.append(("order_date", "<=", params["date_to"]))

        offset, limit, page = paginate()
        total = env["lab.order"].search_count(domain)
        orders = env["lab.order"].search(
            domain, order="order_date desc, id desc", limit=limit, offset=offset
        )
        return ok([_lab_order(o) for o in orders], total=total, page=page, limit=limit)

    @api_route("/lab/orders/<int:order_id>", methods=["GET"])
    def get_lab_order(self, env, key, body, order_id):
        """GET /api/quinze/v1/lab/orders/<id>
        Full lab order detail: samples + all test results with flags.
        تفاصيل طلب المختبر الكاملة: العينات + نتائج الاختبارات مع التنبيهات.
        """
        order = env["lab.order"].browse(order_id)
        if not order.exists():
            return err("Lab order not found. / طلب المختبر غير موجود.", 404)
        return ok(_lab_order(order, detail=True))

    @api_route("/lab/orders/<int:order_id>/result", methods=["POST"], write_required=True)
    def submit_lab_result(self, env, key, body, order_id):
        """POST /api/quinze/v1/lab/orders/<id>/result
        Submit a single test result for a line in this order.
        إدخال نتيجة اختبار واحد في هذا الطلب.

        Body (JSON):
          {
            "line_id": 42,
            "result_value": 5.8,         (for numeric tests)
            "result_text": "No growth",  (for text/culture tests)
            "result_bool": true          (for boolean tests)
          }
        """
        order = env["lab.order"].browse(order_id)
        if not order.exists():
            return err("Lab order not found.", 404)
        if order.state not in ("in_progress", "sample_collected"):
            return err(
                f"Cannot enter result when order state is '{order.state}'. "
                "/ لا يمكن إدخال نتيجة وحالة الطلب هي: "
                f"'{order.state}'.", 400
            )

        line_id = body.get("line_id")
        if not line_id:
            return err("Missing required field: 'line_id'.", 400)

        line = env["lab.order.line"].browse(int(line_id))
        if not line.exists() or line.order_id.id != order_id:
            return err("Line not found in this order. / السطر غير موجود في هذا الطلب.", 404)

        # Build write values
        write_vals = {}
        if "result_value" in body:
            write_vals["result_value"] = float(body["result_value"])
        if "result_text" in body:
            write_vals["result_text"] = str(body["result_text"])
        if "result_bool" in body:
            write_vals["result_bool"] = bool(body["result_bool"])

        if not write_vals:
            return err("Provide at least one result field. / يُرجى تقديم نتيجة واحدة على الأقل.", 400)

        line.write(write_vals)
        line.action_enter_result()   # sets state=resulted, triggers _auto_complete

        return ok({
            "line_id": line.id,
            "state": line.state,
            "flag": line.flag,
            "order_state": order.state,
        })

    # ── Lab Test Catalog ───────────────────────────────────────────────────────

    @api_route("/lab/tests", methods=["GET"])
    def list_lab_tests(self, env, key, body):
        """GET /api/quinze/v1/lab/tests
        Return the lab test catalog.
        إرجاع كتالوج الاختبارات المتاحة.

        Query params:
          ?q=<name or code>   — search by name or code
          ?category_id=<id>
          ?sample_type=blood_venous|urine|...
          ?page=1&limit=50
        """
        domain = [("active", "=", True)]
        params = request.params
        if params.get("q"):
            q = params["q"]
            domain.append("|")
            domain.append(("name", "ilike", q))
            domain.append(("code", "ilike", q))
        if params.get("category_id"):
            try:
                domain.append(("category_id", "=", int(params["category_id"])))
            except ValueError:
                return err("Invalid category_id.", 400)
        if params.get("sample_type"):
            domain.append(("sample_type", "=", params["sample_type"]))

        offset, limit, page = paginate()
        total = env["lab.test"].search_count(domain)
        tests = env["lab.test"].search(
            domain, order="category_id, code", limit=limit, offset=offset
        )
        return ok([_lab_test(t) for t in tests], total=total, page=page, limit=limit)
