from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    rental_period_display = fields.Char(
        string='Period',
        compute='_compute_rental_period_display',
    )
    is_rental_invoice = fields.Boolean(
        string='Is Rental Invoice',
        compute='_compute_is_rental_invoice',
    )
    rental_property_unit_display = fields.Char(
        string='Property Unit',
        compute='_compute_rental_property_unit_display',
    )

    def _compute_is_rental_invoice(self):
        for move in self:
            move.is_rental_invoice = any(
                line.sale_line_ids.filtered(
                    lambda so_line: so_line.order_id.is_rental_order
                )
                for line in move.invoice_line_ids
            )

    def _compute_rental_period_display(self):
        for move in self:
            period_ranges = set()
            for line in move.invoice_line_ids:
                for sale_line in line.sale_line_ids:
                    if not sale_line.order_id.is_rental_order:
                        continue
                    for period in sale_line.invoiced_period_ids.filtered(
                        lambda p: p.invoice_id == move
                    ):
                        if period.period_start_date and period.period_end_date:
                            period_ranges.add(
                                f"{fields.Date.to_string(period.period_start_date)} - "
                                f"{fields.Date.to_string(period.period_end_date)}"
                            )

            move.rental_period_display = ', '.join(sorted(period_ranges)) if period_ranges else False

    def _compute_rental_property_unit_display(self):
        for move in self:
            property_units = set()
            for line in move.invoice_line_ids:
                for sale_line in line.sale_line_ids:
                    order = sale_line.order_id
                    if not order.is_rental_order:
                        continue
                    product = order.property_unit_product_id
                    if product and product.name:
                        property_units.add(product.name)

            move.rental_property_unit_display = ', '.join(sorted(property_units)) if property_units else False

    @api.depends_context('lang')
    @api.depends(
        'invoice_line_ids.currency_rate',
        'invoice_line_ids.tax_base_amount',
        'invoice_line_ids.tax_line_id',
        'invoice_line_ids.price_total',
        'invoice_line_ids.price_subtotal',
        'invoice_payment_term_id',
        'partner_id',
        'currency_id',
    )
    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        for move in self:
            if move.is_rental_invoice and move.tax_totals:
                tax_totals = move.tax_totals
                for subtotal in tax_totals.get('subtotals', []):
                    if subtotal.get('name') == _("Untaxed Amount"):
                        subtotal['name'] = _("Base Amount")
                move.tax_totals = tax_totals


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    price_tax = fields.Monetary(
        string='Tax Amount',
        compute='_compute_price_tax',
        currency_field='currency_id',
        store=False,
    )

    @api.depends('price_subtotal', 'price_total')
    def _compute_price_tax(self):
        for line in self:
            line.price_tax = line.price_total - line.price_subtotal
