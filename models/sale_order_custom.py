from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    state = fields.Selection(selection_add=[
        ('proposal', 'Proposal'),
        ('draft', 'Submitted for Review'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('cancel', 'Cancelled'),
    ])

    # @api.model
    # def default_get(self, fields_list):
    #     res = super().default_get(fields_list)
    #     if self.env.context.get('from_industry_real_estate'):
    #         res['state'] = 'proposal'
    #     return res

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        print("\n=== DEFAULT_GET TRIGGERED ===")
        print("Context:", self.env.context)
        print("Result before modification:", res)
        if self.env.context.get('from_industry_real_estate'):
            res['state'] = 'proposal'
            print("→ Setting state to 'proposal'")
        print("Result after modification:", res)
        print("=============================\n")
        return res


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self.env.context.get('from_industry_real_estate') and not vals.get('state'):
                vals['state'] = 'proposal'
        return super().create(vals_list)

    # FROM ENTERPRISE
    # SALE_ORDER_STATE = [
    #     ('draft', "Quotation"),
    #     ('sent', "Quotation Sent"),
    #     ('sale', "Sales Order"),
    #     ('cancel', "Cancelled"),
    # ]

    def action_submit_proposal(self):
        """Submit proposal to supervisor."""
        for order in self:
            order.state = 'draft'

    def action_submit_to_sent(self):
        """After approval, open email wizard to send quotation."""
        for order in self:
            if order.state != 'draft':
                raise UserError(_("Only submitted proposals can be sent.")) 
        # directly reuse Odoo's existing send flow
        return self.action_quotation_send()
