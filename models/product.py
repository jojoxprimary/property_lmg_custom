from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    property_type = fields.Selection(
        selection=[
            ('residential', 'Residential'),
            ('commercial', 'Commercial'),
        ],
        string='Property Type',
    )