from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class SaleOrderCancel(models.TransientModel):
    _inherit = 'sale.order.cancel'

    @api.model
    def default_get(self, fields_list):
        """Override to set custom template for rental orders."""
        res = super().default_get(fields_list)
        
        # Get the orders being cancelled
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            orders = self.env['sale.order'].browse(active_ids)
            rental_orders = orders.filtered(lambda so: so.is_rental_order)
            
            # If all orders are rental, use custom template
            if rental_orders and len(rental_orders) == len(orders):
                custom_template = self.env.ref(
                    'property_lmg_custom.mail_template_sale_cancellation',
                    raise_if_not_found=False
                )
                if custom_template and 'template_id' in fields_list:
                    res['template_id'] = custom_template.id
        
        return res
