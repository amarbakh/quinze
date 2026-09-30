# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
"""
Health Appointment
موعد طبي

Free-datetime scheduling (per OQ-04) with doctor AND room conflict
prevention.  State machine:
  draft → confirmed → in_progress → done
         ↘ cancelled        ↗ no_show

التحقق من تعارض الأوقات للطبيب والغرفة.
"""
from __future__ import annotations

from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError


class HealthAppointment(models.Model):
    """Scheduled appointment between patient and doctor.

    موعد مجدول بين المريض والطبيب.
    """

    _name = 'health.appointment'
    _description = 'Health Appointment / موعد طبي'
    _inherit = ['health.mixin']
    _order = 'start_datetime desc'
    _rec_name = 'appointment_number'

    STATE_SELECTION = [
        ('draft',       'Draft / مسودة'),
        ('confirmed',   'Confirmed / مؤكد'),
        ('in_progress', 'In Progress / جارٍ'),
        ('done',        'Done / منتهٍ'),
        ('cancelled',   'Cancelled / ملغى'),
        ('no_show',     'No-Show / غياب'),
    ]

    # ── Identity ──────────────────────────────────────────────────────────
    appointment_number: fields.Char = fields.Char(
        string='Appointment No. / رقم الموعد',
        readonly=True,
        copy=False,
        index=True,
        default='New',
        tracking=True,
    )
    state: fields.Selection = fields.Selection(
        selection=STATE_SELECTION,
        string='Status / الحالة',
        default='draft',
        required=True,
        index=True,
        tracking=True,
    )
    color: fields.Integer = fields.Integer(
        string='Color',
        compute='_compute_color',
    )

    # ── Participants ──────────────────────────────────────────────────────
    patient_id: fields.Many2one = fields.Many2one(
        comodel_name='health.patient',
        string='Patient / المريض',
        required=True,
        index=True,
        ondelete='restrict',
        tracking=True,
    )
    doctor_id: fields.Many2one = fields.Many2one(
        comodel_name='res.partner',
        string='Doctor / الطبيب',
        required=True,
        index=True,
        domain="[('is_doctor', '=', True)]",
        ondelete='restrict',
        tracking=True,
    )
    specialty_id: fields.Many2one = fields.Many2one(
        comodel_name='health.specialty',
        string='Specialty / التخصص',
        related='doctor_id.specialty_id',
        store=True,
        readonly=True,
        index=True,
    )
    room_id: fields.Many2one = fields.Many2one(
        comodel_name='health.room',
        string='Room / الغرفة',
        index=True,
        ondelete='restrict',
        domain="[('room_type', 'in', ['consultation', 'examination', 'procedure'])]",
        tracking=True,
    )

    # ── Scheduling ────────────────────────────────────────────────────────
    start_datetime: fields.Datetime = fields.Datetime(
        string='Start / البداية',
        required=True,
        index=True,
        tracking=True,
    )
    stop_datetime: fields.Datetime = fields.Datetime(
        string='End / النهاية',
        required=True,
        tracking=True,
    )
    duration: fields.Float = fields.Float(
        string='Duration (min) / المدة (دقيقة)',
        compute='_compute_duration',
        store=True,
    )

    # ── Clinical ──────────────────────────────────────────────────────────
    chief_complaint: fields.Text = fields.Text(
        string='Chief Complaint / الشكوى الرئيسية',
        tracking=True,
    )
    appointment_type: fields.Selection = fields.Selection(
        selection=[
            ('first_visit',  'First Visit / زيارة أولى'),
            ('follow_up',    'Follow-up / متابعة'),
            ('emergency',    'Emergency / طارئ'),
            ('routine',      'Routine Check / فحص روتيني'),
            ('procedure',    'Procedure / إجراء'),
        ],
        string='Type / النوع',
        default='first_visit',
        tracking=True,
    )

    # ── Linked encounter ──────────────────────────────────────────────────
    encounter_id: fields.Many2one = fields.Many2one(
        comodel_name='health.encounter',
        string='Encounter / الزيارة',
        readonly=True,
        copy=False,
        ondelete='set null',
    )

    # ── Computed ──────────────────────────────────────────────────────────

    @api.depends('start_datetime', 'stop_datetime')
    def _compute_duration(self) -> None:
        for rec in self:
            if rec.start_datetime and rec.stop_datetime:
                delta = rec.stop_datetime - rec.start_datetime
                rec.duration = delta.total_seconds() / 60
            else:
                rec.duration = 0.0

    def _compute_color(self) -> None:
        """Kanban/calendar color by state.

        لون الكانبان/التقويم حسب الحالة.
        """
        STATE_COLOR = {
            'draft': 0, 'confirmed': 4, 'in_progress': 10,
            'done': 20, 'cancelled': 1, 'no_show': 2,
        }
        for rec in self:
            rec.color = STATE_COLOR.get(rec.state, 0)

    # ── ORM hooks ─────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> 'HealthAppointment':
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('appointment_number', 'New') == 'New':
                vals['appointment_number'] = seq.next_by_code(
                    'health.appointment'
                ) or 'New'
        return super().create(vals_list)

    # ── Constraints ───────────────────────────────────────────────────────

    @api.constrains('start_datetime', 'stop_datetime')
    def _check_dates(self) -> None:
        """Stop must be after start.

        يجب أن يكون وقت الانتهاء بعد وقت البدء.
        """
        for rec in self:
            if rec.start_datetime and rec.stop_datetime:
                if rec.stop_datetime <= rec.start_datetime:
                    raise ValidationError(
                        'Appointment end time must be after start time.\n'
                        'وقت انتهاء الموعد يجب أن يكون بعد وقت البدء.'
                    )

    @api.constrains('doctor_id', 'start_datetime', 'stop_datetime', 'state')
    def _check_doctor_conflict(self) -> None:
        """Prevent double-booking the same doctor.

        منع حجز نفس الطبيب في وقتين متداخلين.
        """
        for rec in self:
            if rec.state in ('cancelled', 'no_show'):
                continue
            if not (rec.doctor_id and rec.start_datetime and rec.stop_datetime):
                continue
            conflict = self.search_count([
                ('id', '!=', rec.id),
                ('doctor_id', '=', rec.doctor_id.id),
                ('state', 'not in', ['cancelled', 'no_show']),
                ('start_datetime', '<', rec.stop_datetime),
                ('stop_datetime', '>', rec.start_datetime),
            ])
            if conflict:
                raise ValidationError(
                    f'Doctor {rec.doctor_id.name} already has an appointment '
                    f'during this time slot.\n'
                    f'الطبيب {rec.doctor_id.name} لديه موعد بالفعل خلال هذه الفترة.'
                )

    @api.constrains('room_id', 'start_datetime', 'stop_datetime', 'state')
    def _check_room_conflict(self) -> None:
        """Prevent double-booking the same room.

        منع حجز نفس الغرفة في وقتين متداخلين.
        """
        for rec in self:
            if rec.state in ('cancelled', 'no_show') or not rec.room_id:
                continue
            if not (rec.start_datetime and rec.stop_datetime):
                continue
            conflict = self.search_count([
                ('id', '!=', rec.id),
                ('room_id', '=', rec.room_id.id),
                ('state', 'not in', ['cancelled', 'no_show']),
                ('start_datetime', '<', rec.stop_datetime),
                ('stop_datetime', '>', rec.start_datetime),
            ])
            if conflict:
                raise ValidationError(
                    f'Room "{rec.room_id.name}" is already booked during '
                    f'this time slot.\n'
                    f'الغرفة "{rec.room_id.name}" محجوزة بالفعل خلال هذه الفترة.'
                )

    # ── State transition actions ───────────────────────────────────────────

    def action_confirm(self) -> None:
        """Confirm the appointment: draft → confirmed.

        تأكيد الموعد: مسودة → مؤكد.
        """
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    'Only draft appointments can be confirmed.\n'
                    'يمكن تأكيد المواعيد في المسودة فقط.'
                )
            rec.write({'state': 'confirmed'})

    def action_arrive(self) -> None:
        """Mark patient as arrived: confirmed → in_progress.

        تسجيل وصول المريض: مؤكد → جارٍ.
        """
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(
                    'Only confirmed appointments can be set to in-progress.\n'
                    'يمكن تعيين المواعيد المؤكدة فقط كـ"جارٍ".'
                )
            rec.write({'state': 'in_progress'})

    def action_open_encounter(self) -> dict:
        """Create (or open) linked encounter and transition to in_progress.

        إنشاء (أو فتح) الزيارة المرتبطة والانتقال إلى "جارٍ".
        """
        self.ensure_one()
        if self.state not in ('confirmed', 'in_progress'):
            raise UserError(
                'Appointment must be confirmed before opening an encounter.\n'
                'يجب تأكيد الموعد قبل فتح الزيارة.'
            )
        if not self.encounter_id:
            encounter = self.env['health.encounter'].create({
                'patient_id': self.patient_id.id,
                'appointment_id': self.id,
                'doctor_id': self.doctor_id.id,
                'chief_complaint': self.chief_complaint or '',
                'company_id': self.company_id.id,
                'branch_id': self.branch_id.id or False,
            })
            self.write({'encounter_id': encounter.id, 'state': 'in_progress'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'health.encounter',
            'res_id': self.encounter_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_done(self) -> None:
        """Mark appointment as done: in_progress → done.

        إتمام الموعد: جارٍ → منتهٍ.
        """
        for rec in self:
            if rec.state not in ('in_progress', 'confirmed'):
                raise UserError(
                    'Appointment must be in progress to mark as done.\n'
                    'يجب أن يكون الموعد جارياً لتعيينه كـ"منتهٍ".'
                )
            rec.write({'state': 'done'})

    def action_cancel(self) -> None:
        """Cancel the appointment.

        إلغاء الموعد.
        """
        for rec in self:
            if rec.state == 'invoiced':
                raise UserError(
                    'Invoiced appointments cannot be cancelled.\n'
                    'لا يمكن إلغاء المواعيد المفوترة.'
                )
            rec.write({'state': 'cancelled'})

    def action_no_show(self) -> None:
        """Mark as no-show.

        تعيين حالة الغياب.
        """
        for rec in self:
            rec.write({'state': 'no_show'})

    def action_reset_draft(self) -> None:
        """Reset cancelled appointment to draft.

        إعادة تعيين الموعد الملغى إلى المسودة.
        """
        for rec in self:
            if rec.state not in ('cancelled', 'no_show'):
                raise UserError(
                    'Only cancelled or no-show appointments can be reset.\n'
                    'يمكن إعادة تعيين المواعيد الملغاة أو الغائبة فقط.'
                )
            rec.write({'state': 'draft'})
