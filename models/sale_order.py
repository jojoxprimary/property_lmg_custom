from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    substate_id = fields.Many2one('base.substate', string="Substate")
    substate_name = fields.Char(string="Substate Name", compute="_compute_substate_name", store=False)
    payment_attachment = fields.Binary(string="Payment Attachment")

    # TO GET SUBSTATE NAME FOR VIEW PURPOSES
    @api.depends('substate_id')
    def _compute_substate_name(self):
        for order in self:
            order.substate_name = order.substate_id.name or ''

    # SUBMIT FOR REVIEW BUTTON/ACTION -> FROM PROPOSAL TO FOR REVIEW
    def action_send_for_review(self):
        """Set substate to 'For Review' only."""
        substate = self.env['base.substate'].search([
            ('name', '=', 'For Review'), 
            ('model', '=', 'sale.order'),
        ], limit=1)
        if substate:
            self.substate_id = substate.id

    # OVERRIDE QUOTATION SEND TO SET SUBSTATE TO WAITING FOR SIGNATURE
    def action_quotation_send(self):
        res = super().action_quotation_send()
        waiting_substate = self.env['base.substate'].search([
            ('name', '=', 'Waiting for Signature'),
            ('model', '=', 'sale.order'),
        ], limit=1)

        for order in self.filtered(lambda o: o.state == 'sent'):
            if waiting_substate:
                order.substate_id = waiting_substate.id
        return res

    # OVERRIDE VALIDATE ORDER TO SET SUBSTATE TO SIGNED WHEN SIGNATURE RECEIVED
    def _validate_order(self):
        """Prevent automatic confirmation when signature received, set substate instead."""
        for order in self:
            # find your "Signed" substate
            signed_substate = self.env['base.substate'].search([
                ('name', '=', 'Signed'),
                ('model', '=', 'sale.order')
            ], limit=1)
            if signed_substate:
                order.substate_id = signed_substate.id

            # Keep it under "Quotation Sent"
            if order.state == 'draft':
                order.state = 'sent'
    
    # FOR CONFIRM PAYMENT BUTTON/ACTION -> FROM SIGNED TO PAYMENT CONFIRMED
    def action_confirm_payment(self):
        for order in self:
            if not order.payment_attachment:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Missing Attachment',
                        'message': 'Please upload a payment attachment before confirming payment.',
                        'sticky': False,
                        'type': 'warning',
                    }
                }

            if order.substate_name != 'Signed':
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Invalid State',
                        'message': "You can only confirm payment when the substate is 'Signed'.",
                        'sticky': False,
                        'type': 'danger',
                    }
                }

            payment_confirmed_substate = self.env['base.substate'].search([
                ('name', '=', 'Payment Confirmed'),
                ('model', '=', 'sale.order')
            ], limit=1)

            if not payment_confirmed_substate:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Substate Missing',
                        'message': "Couldn't find substate 'Payment Confirmed'.",
                        'sticky': False,
                        'type': 'warning',
                    }
                }
            # update substate to Payment Confirmed
            order.substate_id = payment_confirmed_substate.id