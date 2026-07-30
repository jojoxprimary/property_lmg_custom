from odoo import fields, models


class RentalOccupant(models.Model):
    _name = 'rental.occupant'
    _description = 'Rental Occupant'
    _order = 'id'

    surname = fields.Char(string='Surname', required=True)
    first_name = fields.Char(string='First Name')
    middle_name = fields.Char(string='Middle Name')
    date_of_birth = fields.Date(string='Date of Birth')
    relationship = fields.Char(string='Relationship')
    contact_number = fields.Char(string='Contact Number')
    order_id = fields.Many2one(
        'sale.order',
        string='Rental Order',
        required=True,
        ondelete='cascade',
    )
