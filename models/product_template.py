from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_property_unit = fields.Boolean(
        string='Property Unit',
    )
    property_type = fields.Selection(
        selection=[
            ('residential', 'Residential'),
            ('commercial', 'Commercial'),
        ],
        string='Property Type',
    )
    space_use = fields.Selection(
        selection=[
            ('residential', 'Residential'),
            ('commercial', 'Commercial'),
        ],
        string='Space Use',
    )
    floor = fields.Integer(
        string='Floor',
    )
    area = fields.Float(
        string='Area (sqm)',
    )
    hand_over_condition_ids = fields.Many2many(
        'hand_over_condition',
        string='Hand Over Condition',
    )
    rent_inclusion_ids = fields.Many2many(
        'rent_inclusion',
        string='Rent Inclusion',
    )
    rent_exclusion_ids = fields.Many2many(
        'rent_exclusion',
        string='Rent Exclusions',
    )
    requirements_before_movein = fields.Html(
        string='Requirements Before Move-in',
        sanitize=False,
    )


