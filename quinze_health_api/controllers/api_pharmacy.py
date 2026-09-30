# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
api_pharmacy.py — Pharmacy REST Endpoints
==========================================
نقاط نهاية REST للصيدلية

Routes (prefix: /api/quinze/v1):
  GET  /pharmacy/medications          — catalog of medications (is_medication=True)
  GET  /pharmacy/dispensings          — list dispensings (filters: type, state, patient_id)
  POST /pharmacy/dispensings          — create external dispensing
  GET  /pharmacy/dispensings/<id>     — dispensing detail with lines
  POST /pharmacy/dispensings/<id>/confirm   — confirm dispensing (creates picking + invoice)
  POST /pharmacy/dispensings/<id>/dispense  — dispense (validates picking, posts invoice)
  GET  /pharmacy/claims               — list insurance claims
  POST /pharmacy/claims               — create insurance claim
  GET  /pharmacy/claims/<id>          — claim detail
  POST /pharmacy/claims/<id>/submit   — submit claim to insurer
  POST /pharmacy/claims/<id>/approve  — approve claim
  POST /pharmacy/claims/<id>/reject   — reject claim (body: {"reason": "..."})
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

def _medication(prod) -> dict:
    """Serialize product.template (medication) to dict.
    تحويل منتج دوائي إلى قاموس.
    """
    return {
        "id": prod.id,
        "name": prod.name,
        "generic_name_ar": getattr(prod, "generic_name_ar", "") or "",
        "dosage_form": getattr(prod, "dosage_form", "") or "",
        "strength": getattr(prod, "strength", "") or "",
        "category": _m2o(prod.drug_category_id) if prod.drug_category_id else None,
        "price": prod.list_price,
        "requires_cold_chain": getattr(prod, "requires_cold_chain", False),
        "is_controlled": getattr(prod, "is_controlled", False),
        "tracking": prod.tracking,
    }


def _dispensing(disp, detail=False) -> dict:
    """Serialize pharmacy.dispensing to dict.
    تحويل سجل الصرف إلى قاموس.
    """
    data = {
        "id": disp.id,
        "number": disp.dispensing_number,
        "type": disp.dispensing_type,
        "date": _date(disp.dispensing_date),
        "dispensed_at": _date(disp.dispensed_at),
        "patient": _m2o(disp.patient_id),
        "partner": _m2o(disp.partner_id),
        "pharmacist": _m2o(disp.pharmacist_id),
        "prescription": _m2o(disp.prescription_id),
        "state": disp.state,
        "amount_total": disp.amount_total,
        "currency": disp.currency_id.name if disp.currency_id else "",
        "picking_state": disp.picking_state or "",
        "invoice_state": disp.invoice_state or "",
        "insurance_claim_count": disp.insurance_claim_count,
    }
    if detail:
        data["lines"] = [
            {
                "id": ln.id,
                "product": _m2o(ln.product_id),
                "drug_name_ar": ln.drug_name_ar or "",
                "qty_ordered": ln.qty_ordered,
                "qty_dispensed": ln.qty_dispensed,
                "unit": ln.uom_id.name if ln.uom_id else "",
                "lot": ln.lot_id.name if ln.lot_id else "",
                "expiry_date": _date(ln.expiry_date),
                "price_unit": ln.price_unit,
                "subtotal": ln.subtotal,
                "is_substitution": ln.is_substitution,
                "instructions": ln.instructions or "",
            }
            for ln in disp.line_ids
        ]
    return data


def _claim(claim, detail=False) -> dict:
    """Serialize pharmacy.insurance.claim to dict.
    تحويل مطالبة التأمين إلى قاموس.
    """
    data = {
        "id": claim.id,
        "number": claim.claim_number,
        "dispensing_id": claim.dispensing_id.id,
        "patient": _m2o(claim.patient_id),
        "insurer": claim.insurer_name,
        "policy_number": claim.policy_number or "",
        "member_id": claim.member_id or "",
        "approval_number": claim.approval_number or "",
        "amount_claimed": claim.amount_claimed,
        "coverage_pct": claim.coverage_pct,
        "amount_covered": claim.amount_covered,
        "amount_patient": claim.amount_patient,
        "amount_approved": claim.amount_approved,
        "currency": claim.currency_id.name if claim.currency_id else "",
        "submission_date": _date(claim.submission_date),
        "response_date": _date(claim.response_date),
        "state": claim.state,
    }
    if detail:
        data["rejection_reason"] = claim.rejection_reason or ""
        data["notes"] = claim.notes or ""
    return data


# ── Controller ─────────────────────────────────────────────────────────────────

class PharmacyApiController(QuinzeApiBase):
    """REST endpoints for the Pharmacy module.
    نقاط نهاية REST لوحدة الصيدلية.
    """

    # ── Medications catalog ────────────────────────────────────────────────────

    @api_route("/pharmacy/medications", methods=["GET"])
    def list_medications(self, env, key, body):
        """GET /api/quinze/v1/pharmacy/medications
        Return the medication catalog (is_medication=True products).
        كتالوج الأدوية المتاحة.

        Query params:
          ?q=<name>
          ?category_id=<id>
          ?dosage_form=tablet|capsule|...
          ?page=1&limit=50
        """
        domain = [("is_medication", "=", True), ("active", "=", True)]
        params = request.params
        if params.get("q"):
            domain.append(("name", "ilike", params["q"]))
        if params.get("category_id"):
            try:
                domain.append(("drug_category_id", "=", int(params["category_id"])))
            except ValueError:
                return err("Invalid category_id.", 400)
        if params.get("dosage_form"):
            domain.append(("dosage_form", "=", params["dosage_form"]))

        offset, limit, page = paginate()
        total = env["product.template"].search_count(domain)
        prods = env["product.template"].search(
            domain, order="name", limit=limit, offset=offset
        )
        return ok([_medication(p) for p in prods], total=total, page=page, limit=limit)

    # ── Dispensings ────────────────────────────────────────────────────────────

    @api_route("/pharmacy/dispensings", methods=["GET"])
    def list_dispensings(self, env, key, body):
        """GET /api/quinze/v1/pharmacy/dispensings
        List dispensings with filters.
        قائمة سجلات الصرف مع فلاتر.

        Query params:
          ?type=internal|external
          ?state=draft|confirmed|dispensed|cancelled
          ?patient_id=<id>
          ?date_from=YYYY-MM-DD
          ?date_to=YYYY-MM-DD
          ?page=1&limit=20
        """
        domain = []
        params = request.params
        if params.get("type"):
            domain.append(("dispensing_type", "=", params["type"]))
        if params.get("state"):
            domain.append(("state", "=", params["state"]))
        if params.get("patient_id"):
            try:
                domain.append(("patient_id", "=", int(params["patient_id"])))
            except ValueError:
                return err("Invalid patient_id.", 400)
        if params.get("date_from"):
            domain.append(("dispensing_date", ">=", params["date_from"]))
        if params.get("date_to"):
            domain.append(("dispensing_date", "<=", params["date_to"]))

        offset, limit, page = paginate()
        total = env["pharmacy.dispensing"].search_count(domain)
        disps = env["pharmacy.dispensing"].search(
            domain, order="dispensing_date desc, id desc", limit=limit, offset=offset
        )
        return ok([_dispensing(d) for d in disps], total=total, page=page, limit=limit)

    @api_route("/pharmacy/dispensings", methods=["POST"], write_required=True)
    def create_dispensing(self, env, key, body):
        """POST /api/quinze/v1/pharmacy/dispensings
        Create a new EXTERNAL dispensing (walk-in).
        إنشاء سجل صرف خارجي جديد.

        Body (JSON):
          {
            "partner_id": 10,           — required for external
            "patient_id": 5,            — optional
            "date": "2026-06-01",       — optional, defaults to today
            "lines": [
              {
                "product_id": 7,        — product.product id
                "qty": 10,
                "price_unit": 5.0,
                "instructions": "..."   — optional
              }
            ]
          }
        """
        lines_data = body.get("lines", [])
        if not lines_data:
            return err("At least one medication line is required. / يُرجى إضافة دواء واحد على الأقل.", 400)
        if not body.get("partner_id") and not body.get("patient_id"):
            return err("'partner_id' or 'patient_id' is required. / يُرجى تحديد عميل أو مريض.", 400)

        line_vals = []
        for ln in lines_data:
            if not ln.get("product_id") or not ln.get("qty"):
                return err("Each line requires 'product_id' and 'qty'.", 400)
            line_vals.append((0, 0, {
                "product_id": int(ln["product_id"]),
                "qty_dispensed": float(ln["qty"]),
                "price_unit": float(ln.get("price_unit", 0.0)),
                "instructions": ln.get("instructions", ""),
            }))

        vals = {
            "dispensing_type": "external",
            "line_ids": line_vals,
        }
        if body.get("partner_id"):
            vals["partner_id"] = int(body["partner_id"])
        if body.get("patient_id"):
            vals["patient_id"] = int(body["patient_id"])
        if body.get("date"):
            vals["dispensing_date"] = body["date"]

        disp = env["pharmacy.dispensing"].create(vals)
        return ok(_dispensing(disp, detail=True))

    @api_route("/pharmacy/dispensings/<int:disp_id>", methods=["GET"])
    def get_dispensing(self, env, key, body, disp_id):
        """GET /api/quinze/v1/pharmacy/dispensings/<id>
        Dispensing detail with all medication lines.
        تفاصيل سجل الصرف مع الأدوية.
        """
        disp = env["pharmacy.dispensing"].browse(disp_id)
        if not disp.exists():
            return err("Dispensing not found. / سجل الصرف غير موجود.", 404)
        return ok(_dispensing(disp, detail=True))

    @api_route("/pharmacy/dispensings/<int:disp_id>/confirm",
               methods=["POST"], write_required=True)
    def confirm_dispensing(self, env, key, body, disp_id):
        """POST /api/quinze/v1/pharmacy/dispensings/<id>/confirm
        Confirm the dispensing → creates stock.picking + invoice (external).
        تأكيد الصرف: إنشاء حركة مخزون وفاتورة.
        """
        disp = env["pharmacy.dispensing"].browse(disp_id)
        if not disp.exists():
            return err("Dispensing not found.", 404)
        if disp.state != "draft":
            return err(f"Cannot confirm a dispensing in state '{disp.state}'.", 400)
        disp.action_confirm()
        return ok({"id": disp.id, "state": disp.state,
                   "picking_id": disp.picking_id.id,
                   "invoice_id": disp.invoice_id.id if disp.invoice_id else None})

    @api_route("/pharmacy/dispensings/<int:disp_id>/dispense",
               methods=["POST"], write_required=True)
    def complete_dispensing(self, env, key, body, disp_id):
        """POST /api/quinze/v1/pharmacy/dispensings/<id>/dispense
        Complete dispensing: validates stock picking + posts invoice.
        إتمام الصرف: التحقق من المخزون ونشر الفاتورة.
        """
        disp = env["pharmacy.dispensing"].browse(disp_id)
        if not disp.exists():
            return err("Dispensing not found.", 404)
        if disp.state != "confirmed":
            return err(f"Cannot dispense from state '{disp.state}'.", 400)
        disp.action_dispense()
        return ok({"id": disp.id, "state": disp.state,
                   "dispensed_at": _date(disp.dispensed_at),
                   "invoice_state": disp.invoice_state or ""})

    # ── Insurance Claims ───────────────────────────────────────────────────────

    @api_route("/pharmacy/claims", methods=["GET"])
    def list_claims(self, env, key, body):
        """GET /api/quinze/v1/pharmacy/claims
        List insurance claims with filters.
        قائمة مطالبات التأمين مع فلاتر.

        Query params:
          ?state=draft|submitted|approved|partial|rejected
          ?patient_id=<id>
          ?insurer=<name keyword>
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
        if params.get("insurer"):
            domain.append(("insurer_name", "ilike", params["insurer"]))

        offset, limit, page = paginate()
        total = env["pharmacy.insurance.claim"].search_count(domain)
        claims = env["pharmacy.insurance.claim"].search(
            domain, order="submission_date desc, id desc", limit=limit, offset=offset
        )
        return ok([_claim(c) for c in claims], total=total, page=page, limit=limit)

    @api_route("/pharmacy/claims", methods=["POST"], write_required=True)
    def create_claim(self, env, key, body):
        """POST /api/quinze/v1/pharmacy/claims
        Create an insurance claim for a dispensing.
        إنشاء مطالبة تأمينية لسجل صرف.

        Body (JSON):
          {
            "dispensing_id": 12,
            "insurer_name": "Gulf Insurance Co.",
            "policy_number": "POL-001",
            "member_id": "MBR-999",
            "amount_claimed": 250.0,
            "coverage_pct": 80.0,
            "notes": "..."
          }
        """
        required = ("dispensing_id", "insurer_name", "amount_claimed")
        for f in required:
            if not body.get(f):
                return err(f"Missing required field: '{f}'.", 400)

        vals = {
            "dispensing_id": int(body["dispensing_id"]),
            "insurer_name": body["insurer_name"],
            "amount_claimed": float(body["amount_claimed"]),
            "coverage_pct": float(body.get("coverage_pct", 80.0)),
        }
        for opt in ("policy_number", "member_id", "notes"):
            if body.get(opt):
                vals[opt] = body[opt]

        claim = env["pharmacy.insurance.claim"].create(vals)
        return ok(_claim(claim, detail=True))

    @api_route("/pharmacy/claims/<int:claim_id>", methods=["GET"])
    def get_claim(self, env, key, body, claim_id):
        """GET /api/quinze/v1/pharmacy/claims/<id>"""
        claim = env["pharmacy.insurance.claim"].browse(claim_id)
        if not claim.exists():
            return err("Claim not found. / المطالبة غير موجودة.", 404)
        return ok(_claim(claim, detail=True))

    @api_route("/pharmacy/claims/<int:claim_id>/submit",
               methods=["POST"], write_required=True)
    def submit_claim(self, env, key, body, claim_id):
        """POST /api/quinze/v1/pharmacy/claims/<id>/submit"""
        claim = env["pharmacy.insurance.claim"].browse(claim_id)
        if not claim.exists():
            return err("Claim not found.", 404)
        claim.action_submit()
        return ok({"id": claim.id, "state": claim.state,
                   "submission_date": _date(claim.submission_date)})

    @api_route("/pharmacy/claims/<int:claim_id>/approve",
               methods=["POST"], write_required=True)
    def approve_claim(self, env, key, body, claim_id):
        """POST /api/quinze/v1/pharmacy/claims/<id>/approve
        Body (optional): {"amount_approved": 220.0}
        """
        claim = env["pharmacy.insurance.claim"].browse(claim_id)
        if not claim.exists():
            return err("Claim not found.", 404)
        if body.get("amount_approved"):
            claim.amount_approved = float(body["amount_approved"])
        claim.action_approve()
        return ok({"id": claim.id, "state": claim.state,
                   "amount_approved": claim.amount_approved})

    @api_route("/pharmacy/claims/<int:claim_id>/reject",
               methods=["POST"], write_required=True)
    def reject_claim(self, env, key, body, claim_id):
        """POST /api/quinze/v1/pharmacy/claims/<id>/reject
        Body: {"reason": "Duplicate claim / مطالبة مكررة"}
        """
        claim = env["pharmacy.insurance.claim"].browse(claim_id)
        if not claim.exists():
            return err("Claim not found.", 404)
        reason = body.get("reason", "")
        if not reason:
            return err("'reason' is required for rejection. / سبب الرفض مطلوب.", 400)
        claim.rejection_reason = reason
        claim.action_reject()
        return ok({"id": claim.id, "state": claim.state})
