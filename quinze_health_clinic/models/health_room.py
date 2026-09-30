# -*- coding: utf-8 -*-
# © 2026 Bakhit Alamin — QUINZE Health Suite
"""
Health Room — Examination / Consultation Rooms
غرف الفحص والاستشارات الطبية
"""
from __future__ import annotations

from odoo import fields, models


class HealthRoom(models.Model):
    """Clinical room used for appointments and encounters.

    غرفة سريرية تُستخدم في المواعيد والزيارات.
    """

    _name = 'health.room'
    _description = 'Health Room / غرفة طبية'
    _inherit = ['mail.thread']
    _order = 'name'

    ROOM_TYPE = [
        ('consultation', 'Consultation / استشارة'),
        ('examination',  'Examination / فحص'),
        ('procedure',    'Procedure / إجراء'),
        ('emergency',    'Emergency / طوارئ'),
        ('lab',          'Laboratory / مختبر'),
        ('pharmacy',     'Pharmacy / صيدلية'),
    ]

    name: fields.Char = fields.Char(
        string='Room Name / اسم الغرفة',
        required=True,
        translate=True,
        index=True,
        tracking=True,
    )
    code: fields.Char = fields.Char(
        string='Code / الرمز',
        required=True,
        size=10,
        tracking=True,
    )
    room_type: fields.Selection = fields.Selection(
        selection=ROOM_TYPE,
        string='Type / النوع',
        default='consultation',
        required=True,
        index=True,
    )
    floor: fields.Char = fields.Char(
        string='Floor / الطابق',
        size=20,
    )
    capacity: fields.Integer = fields.Integer(
        string='Capacity / السعة',
        default=1,
    )
    company_id: fields.Many2one = fields.Many2one(
        comodel_name='res.company',
        string='Company / الشركة',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete='restrict',
    )
    branch_id: fields.Many2one = fields.Many2one(
        comodel_name='health.branch',
        string='Branch / الفرع',
        index=True,
        domain="[('active', '=', True)]",
    )
    active: fields.Boolean = fields.Boolean(
        string='Active / نشط',
        default=True,
        tracking=True,
    )

    _sql_constraints = [
        (
            'code_company_unique',
            'UNIQUE(code, company_id)',
            'Room code must be unique per company. '
            '/ رمز الغرفة يجب أن يكون فريداً لكل شركة.',
        ),
    ]
