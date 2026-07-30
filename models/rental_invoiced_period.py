from odoo import api, fields, models


class RentalInvoicedPeriod(models.Model):
    _name = 'rental.invoiced.period'
    _description = 'Rental Invoiced Period'
    _order = 'period_number'

    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Order Line',
        required=True,
        ondelete='cascade',
    )
    period_number = fields.Integer(
        string='Period #',
        required=True,
    )
    period_start_date = fields.Date(
        string='Start Date',
        required=True,
    )
    period_end_date = fields.Date(
        string='End Date',
        required=True,
    )
    amount = fields.Float(
        string='Amount',
        required=True,
    )
    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        readonly=True,
        copy=False,
    )
    invoiced = fields.Boolean(
        string='Invoiced',
        compute='_compute_invoiced',
        store=True,
    )

    @api.depends('invoice_id')
    def _compute_invoiced(self):
        for record in self:
            record.invoiced = bool(record.invoice_id)
