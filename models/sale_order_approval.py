from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _strip_missing_spreadsheet_nodes(self, arch):
        missing_spreadsheet_fields = {
            'spreadsheet_template_id',
            'spreadsheet_id',
        } - set(self._fields)
        if not missing_spreadsheet_fields:
            return arch
        if arch is None:
            return arch

        arch_is_string = isinstance(arch, (str, bytes))
        doc = etree.fromstring(arch) if arch_is_string else arch

        for field_name in missing_spreadsheet_fields:
            for node in doc.xpath("//field[@name='%s']" % field_name):
                parent = node.getparent()
                if parent is not None and parent.tag == 'button' and parent.get('name') == 'action_open_sale_order_spreadsheet':
                    grandparent = parent.getparent()
                    if grandparent is not None:
                        grandparent.remove(parent)
                    continue
                if parent is not None:
                    parent.remove(node)

        for button in doc.xpath("//button[@name='action_open_sale_order_spreadsheet']"):
            parent = button.getparent()
            if parent is not None:
                parent.remove(button)

        return etree.tostring(doc, encoding='unicode') if arch_is_string else doc

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        res['arch'] = self._strip_missing_spreadsheet_nodes(res.get('arch'))
        return res

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        arch = self._strip_missing_spreadsheet_nodes(arch)
        return arch, view

    @api.model
    def get_views(self, views, options=None):
        res = super().get_views(views, options=options)
        fields_views = res.get('fields_views', {})
        for view_data in fields_views.values():
            view_data['arch'] = self._strip_missing_spreadsheet_nodes(view_data.get('arch'))
        return res

    state = fields.Selection(
        selection_add=[
            ('to_approve', 'To Approve'),
            ('sent',),
        ],
    )

    rental_status = fields.Selection(
        selection_add=[
            ('to_approve', 'To Approve'),
            ('sent',),
            ('pickup', 'Booked'),
            ('return', 'Occupied'),
            ('returned', 'Checked Out'),
        ],
    )

    submitted_by_id = fields.Many2one(
        'res.users',
        string='Submitted By',
        readonly=True,
        copy=False,
        help='User who submitted this quotation for approval.',
    )

    is_rental_user_only = fields.Boolean(
        string='Is Rental User Only',
        compute='_compute_is_rental_user_only',
        store=False,
    )

    is_for_manager_review = fields.Boolean(
        string='Is For Manager Review',
        compute='_compute_is_for_manager_review',
        store=False,
    )

    agent_id = fields.Many2one(
        'res.partner',
        string='Agent',
        domain=[('is_company', '=', False)],
        tracking=True,
    )

    occupant_ids = fields.One2many(
        'rental.occupant',
        'order_id',
        string='Person to Occupy',
        copy=False,
    )

    effective_occupy_datetime = fields.Datetime(
        string='Effective Occupy Date',
        readonly=True,
        copy=False,
        help='Actual date/time when the property was occupied.',
    )
    effective_checkout_datetime = fields.Datetime(
        string='Effective Checkout Date',
        readonly=True,
        copy=False,
        help='Actual date/time when the property was checked out.',
    )

    @api.constrains('order_line', 'duration_months')
    def _check_rental_required_fields(self):
        for order in self:
            if order.is_rental_order:
                if not order.property_unit_product_id:
                    raise UserError(_("A Property Unit product is required for rental quotations."))
                if order.duration_months < 2:
                    raise UserError(_("Rental period must be at least 2 months."))

    @api.depends(
        'rental_start_date',
        'rental_return_date',
        'state',
        'order_line.is_rental',
        'order_line.product_uom_qty',
        'order_line.qty_delivered',
        'order_line.qty_returned',
    )
    def _compute_rental_status(self):
        super()._compute_rental_status()
        for order in self:
            if order.is_rental_order and order.state == 'to_approve':
                order.rental_status = 'to_approve'

    def _compute_is_rental_user_only(self):
        user = self.env.user
        is_rental_user = user.has_group('property_lmg_custom.group_rental_user')
        is_rental_manager = user.has_group('property_lmg_custom.group_rental_manager')
        value = is_rental_user and not is_rental_manager
        for order in self:
            order.is_rental_user_only = value

    @api.depends('state', 'is_rental_order')
    def _compute_is_for_manager_review(self):
        for order in self:
            order.is_for_manager_review = order.is_rental_order and order.state == 'to_approve'

    def write(self, vals):
        signature_before = {order.id: bool(order.signature) for order in self if order.is_rental_order}
        blocked_fields = [
            'partner_id', 'order_line', 'note',
            'rental_start_date', 'rental_return_date', 'duration_months',
            'validity_date', 'date_order', 'pricelist_id', 'payment_term_id',
        ]
        is_rental_user_only = self[:1].is_rental_user_only if self else False

        for order in self:
            if order.is_rental_order and order.state == 'to_approve' and is_rental_user_only:
                for field in blocked_fields:
                    if field in vals:
                        raise UserError(
                            _("You cannot modify %s while quotation is pending approval. "
                              "Please wait for manager approval or rejection.") % field
                        )
                order_line = vals.get('order_line', [])
                if order_line:
                    raise UserError(
                        _("You cannot modify order lines while quotation is pending approval. "
                          "Please wait for manager approval or rejection.")
                    )
        result = super().write(vals)
        if vals.get('signature'):
            signed_orders = self.filtered(
                lambda o: o.is_rental_order and not signature_before.get(o.id) and o.signature
            )
            signed_orders._send_client_approved_email()
        return result

    def message_post(self, **kwargs):
        if self.env.context.get('mark_rental_as_sent'):
            self.filtered(lambda o: o.state == 'to_approve').with_context(tracking_disable=True).write({'state': 'sent'})
        return super().message_post(**kwargs)

    def action_submit_for_review(self):
        self.ensure_one()
        if not self.is_rental_order:
            raise UserError(_("Only rental quotations can be submitted for review."))
        self.write({
            'state': 'to_approve',
            'submitted_by_id': self.env.uid,
        })
        self.message_post(
            body=_("Quotation submitted for review by %s", self.env.user.name),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )
        template = self.env.ref('property_lmg_custom.mail_template_rental_approval_request')
        manager_group = self.env.ref('property_lmg_custom.group_rental_manager')
        manager_partners = manager_group.users.mapped('partner_id')
        if manager_partners:
            template.send_mail(
                self.id,
                force_send=True,
                email_values={
                    'recipient_ids': [(6, 0, manager_partners.ids)],
                },
            )
        return True

    def action_approve(self):
        self.ensure_one()
        if not self.env.user.has_group('property_lmg_custom.group_rental_manager'):
            raise UserError(_("Only Rental Managers can approve quotations."))
        self.message_post(
            body=_("Quotation approved by %s", self.env.user.name),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

        template = self.env.ref('property_lmg_custom.mail_template_rental_proposal', raise_if_not_found=False) or self._find_mail_template()
        self._portal_ensure_token()
        ctx = {
            'default_model': 'sale.order',
            'default_res_ids': self.ids,
            'default_composition_mode': 'comment',
            'default_email_add_signature': False,
            'email_notification_allow_footer': False,
            'force_email': True,
            'mark_rental_as_sent': True,
        }
        if template:
            ctx['default_template_id'] = template.id

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    def action_reject(self):
        self.ensure_one()
        if not self.env.user.has_group('property_lmg_custom.group_rental_manager'):
            raise UserError(_("Only Rental Managers can reject quotations."))
        self.write({'state': 'draft'})
        self.message_post(
            body=_("Quotation rejected by %s", self.env.user.name),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )
        if self.submitted_by_id:
            template = self.env.ref('property_lmg_custom.mail_template_rental_rejection')
            template.send_mail(
                self.id,
                force_send=True,
                email_values={
                    'recipient_ids': [(6, 0, [self.submitted_by_id.partner_id.id])],
                },
            )
        return True

    def _send_client_approved_email(self):
        internal_template = self.env.ref('property_lmg_custom.mail_template_rental_client_approved', raise_if_not_found=False)
        client_template = self.env.ref('property_lmg_custom.mail_template_rental_client_thank_you', raise_if_not_found=False)
        manager_group = self.env.ref('property_lmg_custom.group_rental_manager', raise_if_not_found=False)
        manager_partners = manager_group.users.mapped('partner_id') if manager_group else self.env['res.partner']
        for order in self:
            recipient_partners = manager_partners | order.user_id.partner_id | order.submitted_by_id.partner_id
            order.message_post(
                body=_("Client signed the rental proposal."),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
            if internal_template and recipient_partners:
                internal_template.send_mail(
                    order.id,
                    force_send=True,
                    email_values={
                        'recipient_ids': [(6, 0, recipient_partners.ids)],
                    },
                )
            if client_template and order.partner_id:
                client_template.send_mail(
                    order.id,
                    force_send=True,
                    email_values={
                        'recipient_ids': [(6, 0, order.partner_id.ids)],
                    },
                )

    def _send_order_confirmation_mail(self):
        non_rental_orders = self.filtered(lambda o: not o.is_rental_order)
        if non_rental_orders:
            super(SaleOrder, non_rental_orders)._send_order_confirmation_mail()

    @api.depends_context('lang')
    @api.depends('order_line.price_subtotal', 'currency_id', 'company_id', 'payment_term_id', 'is_rental_order')
    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        for order in self:
            if order.is_rental_order and order.tax_totals:
                tax_totals = order.tax_totals
                for subtotal in tax_totals.get('subtotals', []):
                    if subtotal.get('name') == _("Untaxed Amount"):
                        subtotal['name'] = _("Base Amount")
                order.tax_totals = tax_totals
