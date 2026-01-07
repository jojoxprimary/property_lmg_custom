from odoo import models, fields

class CrmLead(models.Model):
    _inherit = "crm.lead"

    contact_id = fields.Many2one(
        "res.partner",
        string="Agent"
    )
