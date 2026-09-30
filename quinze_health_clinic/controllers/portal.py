# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
"""
Patient Portal Controller
متحكم بوابة المريض

Routes:
  /my/health/                  → patient dashboard
  /my/health/appointments      → appointment list
  /my/health/appointments/<id> → appointment detail
  /my/health/prescriptions     → prescription list
  /my/health/prescriptions/<id>→ prescription detail (+ PDF link)

Security: only the portal user whose partner has a linked health.patient
record can access these pages.  Admins and internal users are redirected
to the backend.

الأمان: فقط مستخدم البوابة الذي لدى شريكه سجل health.patient مرتبط
يمكنه الوصول لهذه الصفحات.
"""
from __future__ import annotations

from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import (
    CustomerPortal,
    pager as portal_pager,
)
from odoo.exceptions import AccessError, MissingError


class HealthPortal(CustomerPortal):
    """Extend Odoo's CustomerPortal with patient health pages.

    امتداد بوابة العملاء بصفحات الصحة للمريض.
    """

    # ── Portal home: add health counts to /my dashboard ──────────────────

    def _prepare_home_portal_values(self, counters: list[str]) -> dict:
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        patient = self._get_patient(partner)
        if patient:
            if 'appointment_count' in counters:
                values['appointment_count'] = request.env[
                    'health.appointment'
                ].search_count([
                    ('patient_id', '=', patient.id),
                    ('state', 'not in', ['cancelled', 'no_show']),
                ])
            if 'prescription_count' in counters:
                values['prescription_count'] = request.env[
                    'health.prescription'
                ].search_count([
                    ('patient_id', '=', patient.id),
                    ('state', 'not in', ['cancelled']),
                ])
        return values

    # ── Appointments ──────────────────────────────────────────────────────

    @http.route(
        ['/my/health/appointments', '/my/health/appointments/page/<int:page>'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_appointments(self, page: int = 1, **kwargs) -> object:
        """List patient appointments (paginated).

        قائمة مواعيد المريض (مع تقسيم الصفحات).
        """
        patient = self._get_patient_or_redirect()
        if not patient:
            return request.redirect('/my')

        domain = [
            ('patient_id', '=', patient.id),
            ('state', 'not in', ['cancelled', 'no_show']),
        ]
        Appointment = request.env['health.appointment']
        total = Appointment.search_count(domain)
        pager = portal_pager(
            url='/my/health/appointments',
            total=total,
            page=page,
            step=10,
        )
        appointments = Appointment.search(
            domain,
            order='start_datetime desc',
            limit=10,
            offset=pager['offset'],
        )
        return request.render(
            'quinze_health_clinic.portal_my_appointments',
            {
                'patient': patient,
                'appointments': appointments,
                'pager': pager,
                'page_name': 'appointment',
                'default_url': '/my/health/appointments',
            },
        )

    @http.route(
        '/my/health/appointments/<int:appointment_id>',
        type='http',
        auth='user',
        website=True,
    )
    def portal_appointment_detail(self, appointment_id: int, **kwargs) -> object:
        """Appointment detail page.

        صفحة تفاصيل الموعد.
        """
        patient = self._get_patient_or_redirect()
        if not patient:
            return request.redirect('/my')
        try:
            appointment = self._document_check_access(
                'health.appointment', appointment_id
            )
        except (AccessError, MissingError):
            return request.redirect('/my/health/appointments')
        # Extra safety: only the patient's own appointments
        if appointment.patient_id != patient:
            return request.redirect('/my/health/appointments')
        return request.render(
            'quinze_health_clinic.portal_appointment_detail',
            {
                'appointment': appointment,
                'patient': patient,
                'page_name': 'appointment',
            },
        )

    # ── Prescriptions ─────────────────────────────────────────────────────

    @http.route(
        ['/my/health/prescriptions', '/my/health/prescriptions/page/<int:page>'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_prescriptions(self, page: int = 1, **kwargs) -> object:
        """List patient prescriptions (paginated).

        قائمة وصفات المريض (مع تقسيم الصفحات).
        """
        patient = self._get_patient_or_redirect()
        if not patient:
            return request.redirect('/my')

        domain = [
            ('patient_id', '=', patient.id),
            ('state', 'not in', ['cancelled']),
        ]
        Prescription = request.env['health.prescription']
        total = Prescription.search_count(domain)
        pager = portal_pager(
            url='/my/health/prescriptions',
            total=total,
            page=page,
            step=10,
        )
        prescriptions = Prescription.search(
            domain,
            order='prescription_date desc',
            limit=10,
            offset=pager['offset'],
        )
        return request.render(
            'quinze_health_clinic.portal_my_prescriptions',
            {
                'patient': patient,
                'prescriptions': prescriptions,
                'pager': pager,
                'page_name': 'prescription',
                'default_url': '/my/health/prescriptions',
            },
        )

    @http.route(
        '/my/health/prescriptions/<int:prescription_id>',
        type='http',
        auth='user',
        website=True,
    )
    def portal_prescription_detail(
        self, prescription_id: int, **kwargs
    ) -> object:
        """Prescription detail page with PDF download link.

        صفحة تفاصيل الوصفة مع رابط تنزيل PDF.
        """
        patient = self._get_patient_or_redirect()
        if not patient:
            return request.redirect('/my')
        try:
            prescription = self._document_check_access(
                'health.prescription', prescription_id
            )
        except (AccessError, MissingError):
            return request.redirect('/my/health/prescriptions')
        if prescription.patient_id != patient:
            return request.redirect('/my/health/prescriptions')
        return request.render(
            'quinze_health_clinic.portal_prescription_detail',
            {
                'prescription': prescription,
                'patient': patient,
                'page_name': 'prescription',
            },
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _get_patient(partner) -> object | None:
        """Return the health.patient record for the given partner, or None.

        إرجاع سجل health.patient لشريك معين، أو None.
        """
        if not partner or not partner.is_patient:
            return None
        patient = request.env['health.patient'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        return patient or None

    def _get_patient_or_redirect(self) -> object | None:
        partner = request.env.user.partner_id
        return self._get_patient(partner)
