from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    pending_count = fields.Integer(
        string='Pending Periods',
        compute='_compute_pending_count',
        store=False,
    )

    has_invoiceable_periods = fields.Boolean(
        string='Has Invoiceable Periods',
        compute='_compute_has_invoiceable_periods',
        store=False,
    )

    has_non_rental_to_invoice = fields.Boolean(
        string='Has Non-Rental To Invoice',
        compute='_compute_has_non_rental_to_invoice',
        store=False,
    )

    can_invoice_next_period = fields.Boolean(
        string='Can Invoice Next Period',
        compute='_compute_can_invoice_next_period',
        store=False,
    )

    @api.depends('order_line.qty_to_invoice', 'order_line.is_rental', 'order_line.display_type')
    def _compute_has_non_rental_to_invoice(self):
        for order in self:
            order.has_non_rental_to_invoice = any(
                line.qty_to_invoice > 0 and not line.is_rental and not line.display_type
                for line in order.order_line
            )

    @api.depends('order_line.qty_to_invoice', 'order_line.is_rental', 'order_line.product_id.default_code', 'order_line.product_id.rent_ok', 'order_line.display_type')
    def _compute_can_invoice_next_period(self):
        for order in self:
            rental_lines = order._get_invoice_period_rental_lines()
            if not rental_lines:
                order.can_invoice_next_period = False
                continue

            if not any(line.qty_to_invoice > 0 for line in order.order_line.filtered(lambda l: not l.display_type)):
                order.can_invoice_next_period = False
                continue

            has_period_rows = any(line.invoiced_period_ids for line in rental_lines)
            if not has_period_rows:
                order.can_invoice_next_period = True
                continue

            order.can_invoice_next_period = any(
                line.invoiced_period_ids.filtered(lambda p: not p.invoice_id)
                for line in rental_lines
            )

    @api.depends('order_line.invoiced_period_ids.invoice_id')
    def _compute_pending_count(self):
        for order in self:
            rental_lines = order._get_invoice_period_rental_lines()
            if rental_lines:
                count = sum(
                    len(l.invoiced_period_ids.filtered(lambda p: not p.invoice_id))
                    for l in rental_lines
                )
                order.pending_count = count
            else:
                order.pending_count = 0

    @api.depends(
        'order_line.invoiced_period_ids.invoice_id',
        'order_line.is_rental',
        'order_line.product_id.default_code',
        'order_line.product_id.rent_ok',
        'order_line.display_type',
    )
    def _compute_has_invoiceable_periods(self):
        for order in self:
            rental_lines = order._get_invoice_period_rental_lines()
            if rental_lines:
                pending_count = sum(
                    len(l.invoiced_period_ids.filtered(lambda p: not p.invoice_id))
                    for l in rental_lines
                )
                has_any_period_rows = any(line.invoiced_period_ids for line in rental_lines)
                order.has_invoiceable_periods = pending_count > 0 or not has_any_period_rows
            else:
                order.has_invoiceable_periods = False

    def _get_invoice_period_rental_lines(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda l: not l.display_type and (l.is_rental or l.product_id.rent_ok)
        )

    def _create_invoices(self, grouped=False, final=False, date=None):
        monthly_line_by_order = {}
        for order in self:
            monthly_line = order._get_property_unit_product_line()
            if not monthly_line:
                continue
            monthly_line_by_order[order.id] = monthly_line

        invoices = super()._create_invoices(grouped=grouped, final=final, date=date)

        is_regular_invoice_flow = bool(self.env.context.get('lmg_regular_invoice_flow'))
        if not final and not is_regular_invoice_flow:
            return invoices

        for order in self.filtered(lambda o: o.is_rental_order):
            monthly_line = monthly_line_by_order.get(order.id)
            if not monthly_line:
                continue

            if not monthly_line.invoiced_period_ids:
                monthly_line._generate_periods()
            monthly_line._link_existing_invoices_to_periods()

            order_invoices = invoices.filtered(
                lambda inv: any(sl.order_id == order for sl in inv.invoice_line_ids.sale_line_ids)
                and inv.move_type == 'out_invoice'
                and inv.state != 'cancel'
            )
            if not order_invoices:
                order_invoices = invoices.filtered(
                    lambda inv: inv.move_type == 'out_invoice'
                    and inv.state != 'cancel'
                    and order.name
                    and inv.invoice_origin
                    and order.name in inv.invoice_origin
                )
            if not order_invoices:
                continue

            first_invoice = order_invoices.sorted(
                key=lambda inv: (inv.invoice_date or fields.Date.today(), inv.create_date or fields.Datetime.now(), inv.id)
            )[0]

            target_period = monthly_line.invoiced_period_ids.filtered(
                lambda p: p.invoice_id == first_invoice
            ).sorted('period_number')[:1]
            if not target_period:
                target_period = monthly_line._get_next_pending_period()
            if not target_period:
                continue

            if not target_period.invoice_id:
                target_period.invoice_id = first_invoice.id

            unit_name = order.property_unit_product_id.name if order.property_unit_product_id else _('N/A')
            period_start_str = target_period.period_start_date.strftime('%m/%d/%Y')
            period_end_str = target_period.period_end_date.strftime('%m/%d/%Y')
            period_label = f"{period_start_str} to {period_end_str}"

            invoice_lines = first_invoice.invoice_line_ids.filtered(
                lambda line: monthly_line in line.sale_line_ids and not line.display_type
            )
            if not invoice_lines:
                invoice_lines = first_invoice.invoice_line_ids.filtered(
                    lambda line: line.product_id == monthly_line.product_id and not line.display_type
                )
            for line in invoice_lines:
                line.write({
                    'quantity': 1,
                    'price_unit': target_period.amount,
                    'name': period_label,
                    'sale_line_ids': [(4, monthly_line.id)],
                })

            first_invoice.narration = (
                f"{first_invoice.narration}\nProperty Unit: {unit_name}"
                if first_invoice.narration else f"Property Unit: {unit_name}"
            )

        return invoices

    def action_invoice_next_period(self):
        self.ensure_one()

        rental_line = self._get_property_unit_product_line()
        if not rental_line:
            raise UserError(_("No rental product line found."))

        if not rental_line.invoiced_period_ids:
            rental_line._generate_periods()

        rental_line._link_existing_invoices_to_periods()

        period = rental_line._get_next_pending_period()
        if not period:
            raise UserError(_("All periods have been invoiced."))

        if not any(line.qty_to_invoice > 0 for line in self.order_line.filtered(lambda l: not l.display_type)):
            raise UserError(_("No invoiceable items available. The rental line may have been fully invoiced."))

        invoice = self._create_invoices()
        if not invoice:
            raise UserError(_("Failed to create invoice."))

        invoice = invoice[0]
        unit_name = self.property_unit_product_id.name if self.property_unit_product_id else _('N/A')
        period_label = f"{period.period_start_date.strftime('%m/%d/%Y')} to {period.period_end_date.strftime('%m/%d/%Y')}"

        invoice_lines = invoice.invoice_line_ids.filtered(
            lambda line: rental_line in line.sale_line_ids and not line.display_type
        )
        if not invoice_lines:
            invoice_lines = invoice.invoice_line_ids.filtered(
                lambda line: line.product_id == rental_line.product_id and not line.display_type
            )

        if invoice_lines:
            for line in invoice_lines:
                line.write({
                    'quantity': 1,
                    'price_unit': period.amount,
                    'name': period_label,
                    'sale_line_ids': [(4, rental_line.id)],
                })
        else:
            self.env['account.move.line'].create({
                'move_id': invoice.id,
                'product_id': rental_line.product_id.id,
                'name': period_label,
                'quantity': 1,
                'price_unit': period.amount,
                'sale_line_ids': [(4, rental_line.id)],
            })

        invoice.narration = (
            f"{invoice.narration}\nProperty Unit: {unit_name}"
            if invoice.narration else f"Property Unit: {unit_name}"
        )

        period.invoice_id = invoice.id

        self.message_post(
            body=_("Draft Invoice created for Period %d (%s to %s)") % (
                period.period_number,
                period.period_start_date,
                period.period_end_date,
            ),
            message_type='notification',
        )

        return {
            'type': 'ir.actions.act_url',
            'url': f'/odoo/rental/{self.id}/invoicing/{invoice.id}',
            'target': 'self',
        }
