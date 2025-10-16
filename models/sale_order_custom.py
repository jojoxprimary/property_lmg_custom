from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    state = fields.Selection(selection_add=[
        ('draft', 'Proposal'),
        ('submit', 'Submitted for Review'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('cancel', 'Cancelled'),
    ])

    def action_submit_proposal(self):
        """Submit proposal to supervisor."""
        for order in self:
            order.state = 'submit'

    def action_preview_proposal(self):
        """Open report preview for the proposal."""
        return self.env.ref('sale.action_report_saleorder').report_action(self)
