from odoo import fields, models


class RentInclusion(models.Model):
    _name = 'rent_inclusion'
    _description = 'Rent Inclusion'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(default=True)


class RentExclusion(models.Model):
    _name = 'rent_exclusion'
    _description = 'Rent Exclusion'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(default=True)


class HandOverCondition(models.Model):
    _name = 'hand_over_condition'
    _description = 'Hand Over Condition'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(default=True)
