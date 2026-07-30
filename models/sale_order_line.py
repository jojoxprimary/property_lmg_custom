from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        if (
            self.env.context.get('lmg_regular_invoice_flow')
            and self.order_id.is_rental_order
            and self.product_id.is_property_unit
            and not self.display_type
        ):
            vals['quantity'] = 1
            if not self.invoiced_period_ids:
                self._generate_periods()
            self._link_existing_invoices_to_periods()
            first_period = self._get_next_pending_period()
            if first_period:
                vals['name'] = (
                    f"{first_period.period_start_date.strftime('%m/%d/%Y')} "
                    f"to {first_period.period_end_date.strftime('%m/%d/%Y')}"
                )
        return vals

    rental_product_name = fields.Char(
        string='Rental Product Name',
        compute='_compute_rental_product_name',
        store=False,
    )

    duration = fields.Integer(
        string='Duration',
        compute='_compute_duration',
        store=False,
        help='Rental duration in months (only for rental products)',
    )

    monthly_price = fields.Monetary(
        string='Monthly Price',
        currency_field='currency_id',
    )

    is_property_unit_line = fields.Boolean(
        compute='_compute_is_property_unit_line',
        store=False,
    )

    @api.depends('product_id')
    def _compute_is_property_unit_line(self):
        for line in self:
            line.is_property_unit_line = line.product_id and line.product_id.is_property_unit

    @api.depends('order_id.duration_months', 'is_rental')
    def _compute_duration(self):
        for line in self:
            if line.is_rental and line.order_id and line.order_id.duration_months:
                line.duration = int(line.order_id.duration_months)
            else:
                line.duration = 0

    @api.depends('product_id')
    def _compute_rental_product_name(self):
        rental_codes = ['ADVANCE_RENT', 'SECURITY_DEPOSIT', 'CUSA', 'OTHER_CHARGES']
        for line in self:
            if line.product_id and (line.product_id.is_property_unit or line.product_id.default_code in rental_codes):
                line.rental_product_name = line.product_id.name
            else:
                line.rental_product_name = line.name

    @api.onchange('price_unit')
    def _onchange_price_unit_rental(self):
        if self.product_id and self.product_id.is_property_unit:
            if self.order_id:
                self.order_id._onchange_rental_prices()

    invoiced_period_ids = fields.One2many(
        'rental.invoiced.period',
        'sale_order_line_id',
        string='Invoiced Periods',
    )
    invoiced_count = fields.Integer(
        string='Invoiced Count',
        compute='_compute_invoiced_count',
    )
    pending_count = fields.Integer(
        string='Pending Count',
        compute='_compute_pending_count',
    )

    @api.depends('invoiced_period_ids.invoice_id')
    def _compute_invoiced_count(self):
        for line in self:
            line.invoiced_count = len(line.invoiced_period_ids.filtered(lambda p: p.invoice_id))

    @api.depends('invoiced_period_ids.invoice_id')
    def _compute_pending_count(self):
        for line in self:
            line.pending_count = len(line.invoiced_period_ids.filtered(lambda p: not p.invoice_id))

    def _generate_periods(self):
        self.ensure_one()

        if not self.product_id or not self.product_id.is_property_unit:
            return

        if not self.order_id or not self.order_id.rental_start_date or not self.order_id.rental_return_date:
            return

        self.invoiced_period_ids.unlink()

        start_date = self.order_id.rental_start_date
        end_date = self.order_id.rental_return_date

        diff = relativedelta(end_date, start_date)
        total_months = diff.years * 12 + diff.months
        if diff.days or diff.hours or diff.minutes or diff.seconds:
            total_months += 1
        total_months = max(total_months, 1)

        price = self.price_unit
        if not price or price <= 0:
            return

        period_env = self.env['rental.invoiced.period']
        for i in range(1, total_months + 1):
            period_start = start_date + relativedelta(months=i - 1)
            period_end = start_date + relativedelta(months=i) - relativedelta(days=1)

            period_env.create({
                'sale_order_line_id': self.id,
                'period_number': i,
                'period_start_date': period_start,
                'period_end_date': period_end,
                'amount': price,
            })

        self._link_existing_invoices_to_periods()

    def _link_existing_invoices_to_periods(self):
        self.ensure_one()
        if not self.invoiced_period_ids:
            return

        candidate_moves = self.invoice_lines.mapped('move_id').filtered(
            lambda m: m.move_type == 'out_invoice' and m.state != 'cancel'
        )
        if not candidate_moves:
            return

        moves_in_order = candidate_moves.sorted(
            key=lambda m: (m.invoice_date or fields.Date.today(), m.create_date or fields.Datetime.now(), m.id)
        )
        pending_periods = self.invoiced_period_ids.filtered(lambda p: not p.invoice_id).sorted('period_number')
        if not pending_periods:
            return

        for move in moves_in_order:
            if not pending_periods:
                break
            if self.invoiced_period_ids.filtered(lambda p: p.invoice_id == move):
                continue
            pending_periods[0].invoice_id = move.id
            pending_periods = pending_periods[1:]

    def _get_next_pending_period(self):
        self.ensure_one()
        pending = self.invoiced_period_ids.filtered(lambda p: not p.invoice_id)
        return pending.sorted('period_number')[:1]
