from odoo import models, fields


class RentalSubstate(models.Model):
    _name = 'rental.substate'
    _description = 'Rental Order Substate'

    name = fields.Char(string='Name', required=True)
    model = fields.Char(string='Model')
    sequence = fields.Integer(string='Sequence', default=10)
    is_default = fields.Boolean(string='Default')

    _sql_constraints = [
        ('name_model_uniq', 'unique(name, model)', 'Substate name must be unique per model!'),
    ]
