from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    substate_id = fields.Many2one('base.substate', string="Substate")
    substate_name = fields.Char(string="Substate Name", compute="_compute_substate_name", store=False)

    is_for_manager_review = fields.Boolean(
        string="For Manager Review",
        compute="_compute_is_for_manager_review",
        store=False
    )

    @api.depends('substate_id')
    def _compute_is_for_manager_review(self):
        """Boolean becomes True when:
        - substate is 'For Review'
        - current user is in group_rental_user
        """
        user = self.env.user
        has_group = user.has_group('property_lmg_custom.group_rental_user')

        for order in self:
            order.is_for_manager_review = (
                has_group
                and order.substate_id
                and order.substate_id.name == "For Review"
            )

    # TO UPDATE IF IN RENTAL APP CONTEXT
    is_in_rental = fields.Boolean(
        string="In Rental App",
        compute='_compute_is_in_rental',
        store=False
    )

    # OPTION: IS IN RENTAL - check if we're in rental context
    def _compute_is_in_rental(self):
        for order in self:
            # Check if rental-specific fields exist on the model
            order.is_in_rental = hasattr(order, 'rental_start_date')

    is_rental_order = fields.Boolean(
        string="Is Rental Order",
        compute="_compute_is_rental_order",
        store=True
    )

    @api.depends('order_line', 'order_line.is_rental')
    def _compute_is_rental_order(self):
        for order in self:
            order.is_rental_order = any(line.is_rental for line in order.order_line if hasattr(line, 'is_rental'))


    # TO GET SUBSTATE NAME FOR VIEW PURPOSES
    @api.depends('substate_id')
    def _compute_substate_name(self):
        for order in self:
            order.substate_name = order.substate_id.name or ''
            
    def action_send_for_review(self):
        """Set substate to 'For Review' and email Rental Managers."""
        self.ensure_one()

        # 1. Set substate to "For Review"
        substate = self.env['base.substate'].search([
            ('name', '=', 'For Review'),
            ('model', '=', 'sale.order'),
        ], limit=1)

        if substate:
            self.substate_id = substate.id

        # 2. Load the email template
        template = self.env.ref(
            "property_lmg_custom.mail_template_rental_review_notification",
            raise_if_not_found=False
        )
        if not template:
            raise UserError("Email template not found!")

        # 3. Get all users in the rental manager group
        manager_group = self.env.ref(
            "property_lmg_custom.group_rental_manager",
            raise_if_not_found=False
        )

        if not manager_group:
            raise UserError("Rental Manager group not found!")

        users = manager_group.users
        if not users:
            raise UserError("No users found in Rental Manager group!")

        # 4. Send email to each manager
        for user in users:
            if user.partner_id and user.partner_id.email:
                try:
                    # Use with_context to set the recipient
                    template.with_context(
                        email_to=user.partner_id.email
                    ).send_mail(
                        self.id,
                        force_send=True,
                        email_values={'email_to': user.partner_id.email}
                    )
                except Exception as e:
                    # Log the error but continue with other users
                    _logger.error(f"Failed to send email to {user.name}: {str(e)}")

        return True

    # SEND PROPOSAL BUTTON/ACTION -> SUBSTATE FROM FOR REVIEW TO PROPOSAL SENT
    def action_send_proposal(self):
        """Send proposal email with custom rental proposal template."""
        self.ensure_one()

        self.filtered(lambda so: so.state in ('draft', 'sent')).order_line._validate_analytic_distribution()
        lang = self.env.context.get('lang')

        # GET CUSTOM TEMPLATE
        custom_template = self.env.ref('property_lmg_custom.mail_template_rental_proposal', raise_if_not_found=False)
        if not custom_template:
            custom_template = self.env['mail.template'].search([
                ('name', 'ilike', 'rental proposal'),
                ('model', '=', 'sale.order')
            ], limit=1)
        
        # Use custom or fallback to default
        mail_template = custom_template or self._find_mail_template()

        ctx = {
            'default_model': 'sale.order',
            'default_res_ids': self.ids,
            'default_composition_mode': 'comment',
            'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
            'email_notification_allow_footer': True,
            'proforma': self.env.context.get('proforma', False),
            'is_send_proposal': True,
            'force_email': True,
            'model_description': self.with_context(lang=lang).type_name,
            'mark_so_as_sent': True,
        }

        # Set template if found
        if mail_template:
            ctx['default_template_id'] = mail_template.id
            if mail_template.lang:
                lang = mail_template._render_lang(self.ids)[self.id]
        
        # Ensure portal token
        self._portal_ensure_token()

        action = {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'target': 'new',
            'context': ctx,
        }

        if (
            self.env.context.get('check_document_layout')
            and not self.env.context.get('discard_logo_check')
            and self.env.is_admin()
            and not self.env.company.external_report_layout_id
        ):
            layout_action = self.env['ir.actions.report']._action_configure_external_report_layout(action)
            layout_action['context']['dialog_size'] = 'extra-large'
            return layout_action

        return action

    # MAKE CUSTOM PROPOSAL TEMPLATE THE ONE USED FOR SIGNING AND DOWNLOADING IN PORTAL
    def _get_name_portal_content_view(self):
        """Override to use custom portal HTML template for rental orders"""
        self.ensure_one()
        if self.is_rental_order:
            return 'property_lmg_custom.rent_proposal_portal_content'
        return super()._get_name_portal_content_view()

    def _get_report_base_filename(self):
        """Set custom filename for downloaded PDFs"""
        self.ensure_one()
        
        _logger.info(f"Filename for {self.name} - is_in_rental: {self.is_in_rental}")
        
        # Use is_in_rental since report_name is not available in portal context
        if self.is_rental_order:
            filename = 'Rental_Proposal_%s' % (self.name)
            _logger.info(f"Using rental filename: {filename}")
            return filename
        
        _logger.info(f"Using default filename")
        return super()._get_report_base_filename()


    def action_download_contract(self):
        """Download contract PDF."""
        self.ensure_one()
        
        # Return the standard quotation/order print action
        return self.env.ref('property_lmg_custom.action_report_rent_agreement').report_action(self)
    
    # Custom recurring monthly total field
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
        for order in self:
            # Filter lines for product with recurring_invoice
            recurring_lines = order.order_line.filtered(
                lambda line: line.product_id.recurring_invoice
            )
            
            # Sum only the recurring lines
            order.recurring_monthly_total = sum(recurring_lines.mapped('price_subtotal'))
            
            _logger.info(
                f"Sale Order {order.name}: "
                f"Total lines: {len(order.order_line)}, "
                f"Recurring lines: {len(recurring_lines)}, "
                f"Recurring total: {order.recurring_monthly_total}"
            )
    
    # Convert rental duration from days to months for display
    duration_months = fields.Float(
        string='Duration',
        compute='_compute_duration_months',
        store=True
    )

    @api.depends('duration_days')
    def _compute_duration_months(self):
        for order in self:
            if order.duration_days:
                order.duration_months = int(round(order.duration_days / 30.0))
            else:
                order.duration_months = 0

    # For auto compute advance rent and security deposit depending on monthly rental price
    @api.onchange('order_line')
    def _onchange_rental_prices(self):
        """ Auto-update Security Deposit and Advance Rent prices 
            based on Monthly Rental price   """
        # if no order lines, skip
        if not self.order_line:
            return

         # Find Monthly Rental line by internal reference (default_code)
        monthly_rental_line = self.order_line.filtered(lambda l: l.product_id.default_code == 'MONTHLY_RENTAL')
        if not monthly_rental_line:
            return

        # Get the monthly rental price
        monthly_price = monthly_rental_line[0].price_unit

        # Skip if monthly price is 0 or not set
        if not monthly_price or monthly_price <= 0:
            return

        # Update Security Deposit (2x monthly rent)
        security_deposit_lines = self.order_line.filtered(lambda l: l.product_id.default_code == 'SECURITY_DEPOSIT')

        for line in security_deposit_lines:
            if line.price_unit != monthly_price * 2:
                line.price_unit = monthly_price * 2
                _logger.info(f"Updated Security Deposit line to {line.price_unit}")

        # Update Advance Rent (1x monthly rent)
        advance_rent_lines = self.order_line.filtered(lambda l: l.product_id.default_code == 'ADVANCE_RENT')

        for line in advance_rent_lines:
            if line.price_unit != monthly_price * 1:
                line.price_unit = monthly_price * 1
                _logger.info(f"Updated Advance Rent line to {line.price_unit}")

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    @api.onchange('price_unit')
    def _onchange_price_unit_rental(self):
        """
        Trigger parent order's price update when monthly rental price changes
        """
        if self.product_id and self.product_id.default_code == 'MONTHLY_RENTAL':
            if self.order_id:
                self.order_id