import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    duration_months = fields.Float(
        string='Duration',
        compute='_compute_duration_months',
        store=True,
    )

    show_update_duration = fields.Boolean(
        string='Has Duration Changed',
        store=False,
    )

    inherit_space = fields.Selection(
        selection=[
            ('residential', 'Residential'),
            ('commercial', 'Commercial'),
        ],
        string='Inherit Space',
    )

    property_unit_product_id = fields.Many2one(
        'product.template',
        string='Property Unit Product',
        compute='_compute_property_unit_product_id',
        store=False,
        help="First order line product that has is_property_unit=True.",
    )

    property_unit_display_name = fields.Char(
        string='Property Unit',
        compute='_compute_property_unit_display_name',
        store=True,
    )

    def _get_property_unit_product_line(self):
        for line in self.order_line.filtered(lambda l: not l.display_type):
            if line.product_id.is_property_unit:
                return line
        return self.env['sale.order.line']

    @api.depends('order_line', 'order_line.product_id')
    def _compute_property_unit_product_id(self):
        for order in self:
            line = order._get_property_unit_product_line()
            order.property_unit_product_id = line.product_id.product_tmpl_id if line else False

    @api.depends('property_unit_product_id')
    def _compute_property_unit_display_name(self):
        for order in self:
            product = order.property_unit_product_id
            order.property_unit_display_name = product.name if product else False

    @api.onchange('rental_start_date', 'rental_return_date')
    def _onchange_duration_show_update_duration(self):
        self.show_update_duration = any(line.is_rental for line in self.order_line)
        self._onchange_rental_prices()

    @api.depends('duration_days')
    def _compute_duration_months(self):
        for order in self:
            order.duration_months = int(round(order.duration_days / 30.0)) if order.duration_days else 0

    @api.onchange('order_line')
    def _onchange_detect_property_unit(self):
        property_unit_line = self._get_property_unit_product_line()
        if not property_unit_line:
            return

        stale_monthly = self.order_line.filtered(
            lambda l: not l.display_type and l.product_id.default_code == 'MONTHLY_RENTAL'
        )
        if stale_monthly:
            stale_monthly.unlink()

        product = property_unit_line.product_id

        if product.product_tmpl_id.property_type:
            self.inherit_space = product.product_tmpl_id.property_type

        managed_codes = ['ADVANCE_RENT', 'SECURITY_DEPOSIT', 'CUSA', 'OTHER_CHARGES']
        required_codes = ['ADVANCE_RENT', 'SECURITY_DEPOSIT']
        if self.inherit_space == 'commercial':
            required_codes.extend(['CUSA', 'OTHER_CHARGES'])

        managed_lines = self.order_line.filtered(
            lambda l: not l.display_type and l.product_id.default_code in managed_codes
        )
        lines_to_remove = managed_lines.filtered(
            lambda l: l.product_id.default_code not in required_codes
        )
        if lines_to_remove:
            lines_to_remove.unlink()

        existing_product_codes = set(
            self.order_line.filtered(lambda l: not l.display_type).mapped('product_id.default_code')
        )
        new_codes = [code for code in required_codes if code not in existing_product_codes]

        if new_codes:
            products = self.env['product.product'].search([('default_code', 'in', new_codes)])
            product_by_code = {p.default_code: p for p in products}
            create_commands = []
            for code in new_codes:
                prod = product_by_code.get(code)
                if not prod:
                    _logger.warning("Product not found: %s", code)
                    continue
                vals = {
                    'product_id': prod.id,
                    'product_uom_qty': 1,
                }
                create_commands.append((0, 0, vals))
            if create_commands:
                self.update({'order_line': create_commands})

        self._onchange_rental_prices()

    def _get_monthly_rental_price(self):
        self.ensure_one()
        property_unit_product = self.property_unit_product_id
        if not property_unit_product:
            return 0.0

        pricings = property_unit_product.product_pricing_ids.filtered(
            lambda p: p.recurrence_id.unit == 'month'
        )

        if pricings:
            pricelist = self.pricelist_id
            for pricing in pricings:
                if pricing.pricelist_id == pricelist:
                    return pricing.price / (pricing.recurrence_id.duration or 1)
            for pricing in pricings:
                if not pricing.pricelist_id:
                    return pricing.price / (pricing.recurrence_id.duration or 1)
            return pricings[0].price / (pricings[0].recurrence_id.duration or 1)

        property_unit_line = self._get_property_unit_product_line()
        if property_unit_line and property_unit_line.price_unit:
            return property_unit_line.price_unit
        return property_unit_product.list_price or 0.0

    def _update_rental_prices(self):
        self.ensure_one()
        months = int(self.duration_months or 0)
        if months <= 0:
            months = self._get_rental_duration_months()
        if months <= 0:
            return

        monthly_price = self._get_monthly_rental_price()
        if not monthly_price or monthly_price <= 0:
            return

        for line in self.order_line.filtered(lambda l: not l.display_type):
            product_code = line.product_id.default_code

            if line.product_id.is_property_unit:
                line.price_unit = monthly_price
                line.product_uom_qty = months
                line.monthly_price = monthly_price
            elif product_code == 'SECURITY_DEPOSIT':
                line.price_unit = monthly_price * 2
                line.product_uom_qty = 1
            elif product_code == 'ADVANCE_RENT':
                line.price_unit = monthly_price
                line.product_uom_qty = 1
            elif product_code in ('CUSA', 'OTHER_CHARGES'):
                line.product_uom_qty = months

    def _onchange_rental_prices(self):
        self._update_rental_prices()

    def _sync_rental_prices(self):
        monthly_price = self._get_monthly_rental_price()
        if not monthly_price or monthly_price <= 0:
            return

        property_unit_line = self._get_property_unit_product_line()
        if property_unit_line and property_unit_line.monthly_price != monthly_price:
            property_unit_line.write({'monthly_price': monthly_price})
            _logger.info("Synced Property Unit monthly_price to %s", monthly_price)

        security_deposit_lines = self.order_line.filtered(
            lambda l: l.product_id.default_code == 'SECURITY_DEPOSIT'
        )
        for line in security_deposit_lines:
            expected = monthly_price * 2
            if line.price_unit != expected:
                line.write({'price_unit': expected})
                _logger.info("Synced Security Deposit to %s", expected)

        advance_rent_lines = self.order_line.filtered(
            lambda l: l.product_id.default_code == 'ADVANCE_RENT'
        )
        for line in advance_rent_lines:
            if line.price_unit != monthly_price:
                line.write({'price_unit': monthly_price})
                _logger.info("Synced Advance Rent to %s", monthly_price)

    def _get_rental_duration_months(self):
        self.ensure_one()
        if not self.rental_start_date or not self.rental_return_date:
            return 1
        diff = relativedelta(self.rental_return_date, self.rental_start_date)
        months = diff.years * 12 + diff.months
        if diff.days or diff.hours or diff.minutes or diff.seconds:
            months += 1
        return max(months, 1)

    def action_update_rental_prices(self):
        self.ensure_one()
        self._update_rental_prices()
        months = int(self.duration_months or 0)
        if months <= 0:
            months = self._get_rental_duration_months()
        monthly_price = self._get_monthly_rental_price()
        if months > 0 and monthly_price and monthly_price > 0:
            self.message_post(
                body=_("Rental prices updated: monthly price %s, %d month(s).",
                       monthly_price, months)
            )
