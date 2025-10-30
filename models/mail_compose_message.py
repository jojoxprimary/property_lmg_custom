# In models/mail_compose_message.py
from odoo import models
from odoo.exceptions import UserError

class MailComposer(models.TransientModel):
    _inherit = 'mail.compose.message'

    def action_send_mail(self):
        """Override to change substate when sending from Send Proposal action."""
        # Call the original method first
        result = super().action_send_mail()
        
        # Update substate AFTER sending successfully
        if self.env.context.get('is_send_proposal') and self.model == 'sale.order':
            sale_order_ids = self.env.context.get('default_res_ids', [])
            
            if sale_order_ids:
                sale_orders = self.env['sale.order'].browse(sale_order_ids)
                
                waiting_substate = self.env['base.substate'].search([
                    ('name', '=', 'Waiting for Signature'),
                    ('model', '=', 'sale.order')
                ], limit=1)
                
                if waiting_substate:
                    sale_orders.write({'substate_id': waiting_substate.id})
                else:
                    raise UserError("Substate 'Waiting for Signature' not found. Please configure it in Base Substates.")
        
        return result