from odoo import api, fields, models, _


class RentalOrderWizard(models.TransientModel):
    _inherit = 'rental.order.wizard'

    property_unit_name = fields.Char(
        string='Property Unit',
        compute='_compute_property_unit_name',
        store=False,
    )

    rental_start_date = fields.Datetime(
        related='order_id.rental_start_date',
        string='Period Start',
        readonly=True,
    )
    rental_return_date = fields.Datetime(
        related='order_id.rental_return_date',
        string='Period End',
        readonly=True,
    )

    actual_occupy_datetime = fields.Datetime(
        string='Actual Occupy Date',
        default=fields.Datetime.now,
        help='Actual date/time of occupancy. Defaults to now; adjust if processing late.',
    )
    actual_checkout_datetime = fields.Datetime(
        string='Actual Checkout Date',
        default=fields.Datetime.now,
        help='Actual date/time of checkout. Defaults to now; adjust if processing late.',
    )

    @api.depends('order_id')
    def _compute_property_unit_name(self):
        for wizard in self:
            product = wizard.order_id.property_unit_product_id
            wizard.property_unit_name = product.name if product else False

    def apply(self):
        result = super().apply()
        for wizard in self:
            if wizard.status == 'pickup' and wizard.actual_occupy_datetime:
                wizard.order_id.effective_occupy_datetime = wizard.actual_occupy_datetime
                wizard.order_id.message_post(
                    body=_("Actual occupancy date recorded: %s") % wizard.actual_occupy_datetime,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
            elif wizard.status == 'return' and wizard.actual_checkout_datetime:
                wizard.order_id.effective_checkout_datetime = wizard.actual_checkout_datetime
                wizard.order_id.message_post(
                    body=_("Actual checkout date recorded: %s") % wizard.actual_checkout_datetime,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
        return result


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def _create_invoices(self, sale_orders):
        self.ensure_one()
        if self.advance_payment_method == 'delivered':
            sale_orders = sale_orders.with_context(lmg_regular_invoice_flow=True)
        return super()._create_invoices(sale_orders)

    def create_invoices(self):
        self.ensure_one()
        if self.advance_payment_method == 'delivered':
            return super(
                SaleAdvancePaymentInv,
                self.with_context(lmg_regular_invoice_flow=True),
            ).create_invoices()
        return super().create_invoices()
