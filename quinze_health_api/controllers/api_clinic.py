# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
"""
api_clinic.py — Clinic REST Endpoints
=======================================
نقاط نهاية REST للعيادة

Routes (prefix: /api/quinze/v1):
  GET  /patients                  — list patients (paginated)
  GET  /patients/<id>             — patient detail + active prescriptions
  GET  /appointments              — list appointments (filters: date, state, patient_id)
  POST /appointments              — create appointment
  GET  /appointments/<id>         — appointment detail + encounter summary
  GET  /prescriptions             — list prescriptions (filters: state, patient_id)
  GET  /prescriptions/<id>        — prescription detail with medication lines
"""

from odoo import fields as odoo_fields
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

def _patient(p) -> dict:
    """Serialize health.patient to dict.
    تحويل health.patient إلى قاموس.
    """
    partner = p.partner_id
    return {
        "id": p.id,
        "name": partner.name,
        "national_id": partner.national_id or "",
        "dob": _date(partner.dob),
        "gender": partner.gender or "",
        "blood_type": partner.blood_type or "",
        "phone": partner.phone or "",
        "email": partner.email or "",
        "chronic_conditions": p.chronic_conditions or "",
        "allergies": p.allergy_ids.mapped("name") if hasattr(p, "allergy_ids") else [],
        "active": p.active,
    }


def _appointment(apt, detail=False) -> dict:
    """Serialize health.appointment to dict.
    تحويل health.appointment إلى قاموس.
    """
    data = {
        "id": apt.id,
        "patient": _m2o(apt.patient_id),
        "doctor": _m2o(apt.doctor_id),
        "room": _m2o(apt.room_id) if apt.room_id else None,
        "start": _date(apt.start_datetime),
        "stop": _date(apt.stop_datetime),
        "type": apt.appointment_type,
        "state": apt.state,
        "chief_complaint": apt.chief_complaint or "",
        "priority": apt.priority,
    }
    if detail and apt.encounter_id:
        enc = apt.encounter_id
        data["encounter"] = {
            "id": enc.id,
            "state": enc.state,
            "clinical_notes": enc.clinical_notes or "",
            "diagnosis": enc.diagnosis or "",
        }
    return data


def _prescription(rx, detail=False) -> dict:
    """Serialize health.prescription to dict.
    تحويل health.prescription إلى قاموس.
    """
    data = {
        "id": rx.id,
        "number": rx.prescription_number,
        "patient": _m2o(rx.patient_id),
        "doctor": _m2o(rx.doctor_id),
        "date": _date(rx.prescription_date),
        "valid_until": _date(rx.valid_until),
        "is_expired": rx.is_expired,
        "state": rx.state,
        "dispensing_count": rx.dispensing_count,
    }
    if detail:
        data["lines"] = [
            {
                "id": ln.id,
                "product": _m2o(ln.product_id),
                "drug_name_ar": ln.drug_name_ar or "",
                "dose": ln.dose,
                "frequency": ln.frequency,
                "duration_days": ln.duration_days,
                "route": ln.route or "",
                "qty_to_dispense": ln.qty_to_dispense,
                "dispensed_qty": ln.dispensed_qty,
                "remaining_qty": ln.remaining_qty,
                "line_state": ln.line_dispensing_state,
                "instructions": ln.instructions or "",
            }
            for ln in rx.prescription_line_ids
        ]
    return data


# ── Controller ─────────────────────────────────────────────────────────────────

class ClinicApiController(QuinzeApiBase):
    """REST endpoints for the Clinic module.
    نقاط نهاية REST لوحدة العيادة.
    """

    # ── Patients ───────────────────────────────────────────────────────────────

    @api_route("/patients", methods=["GET"])
    def list_patients(self, env, key, body):
        """GET /api/quinze/v1/patients
        List all active patients with optional search.
        قائمة المرضى النشطين مع خيار البحث.

        Query params:
          ?q=<name>       — search by name
          ?page=1&limit=20
        """
        domain = [("active", "=", True)]
        q = request.params.get("q", "").strip()
        if q:
            domain.append(("partner_id.name", "ilike", q))

        offset, limit, page = paginate()
        total = env["health.patient"].search_count(domain)
        patients = env["health.patient"].search(domain, limit=limit, offset=offset)
        return ok([_patient(p) for p in patients], total=total, page=page, limit=limit)

    @api_route("/patients/<int:patient_id>", methods=["GET"])
    def get_patient(self, env, key, body, patient_id):
        """GET /api/quinze/v1/patients/<id>
        Patient detail with recent prescriptions.
        تفاصيل المريض مع الوصفات الحديثة.
        """
        patient = env["health.patient"].browse(patient_id)
        if not patient.exists():
            return err("Patient not found. / المريض غير موجود.", 404)
        data = _patient(patient)
        # Last 5 prescriptions
        rxs = env["health.prescription"].search(
            [("patient_id", "=", patient_id)],
            order="prescription_date desc",
            limit=5,
        )
        data["recent_prescriptions"] = [_prescription(rx) for rx in rxs]
        return ok(data)

    # ── Appointments ───────────────────────────────────────────────────────────

    @api_route("/appointments", methods=["GET"])
    def list_appointments(self, env, key, body):
        """GET /api/quinze/v1/appointments
        List appointments with optional filters.
        قائمة المواعيد مع فلاتر اختيارية.

        Query params:
          ?state=confirmed|done|cancelled
          ?patient_id=<id>
          ?doctor_id=<id>
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
        if params.get("doctor_id"):
            try:
                domain.append(("doctor_id", "=", int(params["doctor_id"])))
            except ValueError:
                return err("Invalid doctor_id.", 400)
        if params.get("date_from"):
            domain.append(("start_datetime", ">=", f"{params['date_from']} 00:00:00"))
        if params.get("date_to"):
            domain.append(("start_datetime", "<=", f"{params['date_to']} 23:59:59"))

        offset, limit, page = paginate()
        total = env["health.appointment"].search_count(domain)
        apts = env["health.appointment"].search(
            domain, order="start_datetime desc", limit=limit, offset=offset
        )
        return ok([_appointment(a) for a in apts], total=total, page=page, limit=limit)

    @api_route("/appointments", methods=["POST"], write_required=True)
    def create_appointment(self, env, key, body):
        """POST /api/quinze/v1/appointments
        Create a new appointment.
        إنشاء موعد جديد.

        Body (JSON):
          {
            "patient_id": 5,
            "doctor_id": 3,
            "start": "2026-06-01T09:00:00",
            "stop":  "2026-06-01T09:30:00",
            "type":  "new|follow_up|emergency",
            "chief_complaint": "...",
            "room_id": 2            (optional)
          }
        """
        required = ("patient_id", "doctor_id", "start", "stop")
        for f in required:
            if not body.get(f):
                return err(f"Missing required field: '{f}'.", 400)

        try:
            vals = {
                "patient_id": int(body["patient_id"]),
                "doctor_id": int(body["doctor_id"]),
                "start_datetime": body["start"],
                "stop_datetime": body["stop"],
                "appointment_type": body.get("type", "new"),
                "chief_complaint": body.get("chief_complaint", ""),
            }
            if body.get("room_id"):
                vals["room_id"] = int(body["room_id"])
        except (ValueError, KeyError) as exc:
            return err(f"Invalid field value: {exc}", 400)

        apt = env["health.appointment"].create(vals)
        return ok(_appointment(apt), total=None)

    @api_route("/appointments/<int:apt_id>", methods=["GET"])
    def get_appointment(self, env, key, body, apt_id):
        """GET /api/quinze/v1/appointments/<id>
        Appointment detail including encounter summary if available.
        تفاصيل الموعد مع ملخص الزيارة السريرية إذا وُجدت.
        """
        apt = env["health.appointment"].browse(apt_id)
        if not apt.exists():
            return err("Appointment not found. / الموعد غير موجود.", 404)
        return ok(_appointment(apt, detail=True))

    # ── Prescriptions ──────────────────────────────────────────────────────────

    @api_route("/prescriptions", methods=["GET"])
    def list_prescriptions(self, env, key, body):
        """GET /api/quinze/v1/prescriptions
        List prescriptions with optional filters.
        قائمة الوصفات مع فلاتر اختيارية.

        Query params:
          ?state=draft|confirmed|partially_dispensed|dispensed|cancelled
          ?patient_id=<id>
          ?active_only=1  (only confirmed + partially_dispensed, not expired)
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
        if params.get("active_only"):
            domain += [
                ("state", "in", ["confirmed", "partially_dispensed"]),
                ("is_expired", "=", False),
            ]

        offset, limit, page = paginate()
        total = env["health.prescription"].search_count(domain)
        rxs = env["health.prescription"].search(
            domain, order="prescription_date desc", limit=limit, offset=offset
        )
        return ok([_prescription(rx) for rx in rxs], total=total, page=page, limit=limit)

    @api_route("/prescriptions/<int:rx_id>", methods=["GET"])
    def get_prescription(self, env, key, body, rx_id):
        """GET /api/quinze/v1/prescriptions/<id>
        Prescription detail with all medication lines.
        تفاصيل الوصفة مع جميع أسطر الأدوية.
        """
        rx = env["health.prescription"].browse(rx_id)
        if not rx.exists():
            return err("Prescription not found. / الوصفة غير موجودة.", 404)
        return ok(_prescription(rx, detail=True))
