# models/sale_subscription.py

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class SaleSubscription(models.Model):
    _inherit = 'sale.subscription'
    
    recurring_monthly_total = fields.Monetary(
        string="Monthly Recurring Total",
        compute="_compute_recurring_monthly_total",
        store=True,
        currency_field='currency_id',
        help="Total amount of only recurring/subscription products (excluding one-time payments)"
    )
    
    @api.depends('order_line', 'order_line.price_subtotal', 'order_line.product_id.recurring_invoice')
    def _compute_recurring_monthly_total(self):
        """Calculate total of ONLY recurring/subscription products"""
        for subscription in self:
            # Filter lines where product is marked as recurring
            recurring_lines = subscription.order_line.filtered(
                lambda line: line.product_id.recurring_invoice
            )
            
            # Sum only the recurring lines
            subscription.recurring_monthly_total = sum(recurring_lines.mapped('price_subtotal'))
            
            _logger.info(
                f"Subscription {subscription.name}: "
                f"Total lines: {len(subscription.order_line)}, "
                f"Recurring lines: {len(recurring_lines)}, "
                f"Recurring total: {subscription.recurring_monthly_total}"
            )