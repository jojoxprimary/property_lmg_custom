from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ===========================
    # FIELDS
    # ===========================
    
    substate_id = fields.Many2one('base.substate', string="Substate")
    substate_name = fields.Char(
        string="Substate Name",
        compute="_compute_substate_name",
        store=False
    )
    
    is_for_manager_review = fields.Boolean(
        string="For Manager Review",
        compute="_compute_is_for_manager_review",
        store=False
    )
    
    is_in_rental = fields.Boolean(
        string="In Rental App",
        compute='_compute_is_in_rental',
        store=False
    )
    
    is_rental_order = fields.Boolean(
        string="Is Rental Order",
        compute="_compute_is_rental_order",
        store=True
    )
    
    recurring_monthly_total = fields.Monetary(
        string="Monthly Recurring Total",
        compute="_compute_recurring_monthly_total",
        store=True,
        currency_field='currency_id',
        help="Total amount of only recurring/subscription products (excluding one-time payments)"
    )
    
    duration_months = fields.Float(
        string='Duration',
        compute='_compute_duration_months',
        store=True
    )

    # ===========================
    # COMPUTE METHODS
    # ===========================
    
    @api.depends('substate_id')
    def _compute_substate_name(self):
        """Get substate name for view purposes."""
        for order in self:
            order.substate_name = order.substate_id.name or ''
    
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
    
    def _compute_is_in_rental(self):
        """Check if we're in rental context by checking for rental-specific fields."""
        for order in self:
            order.is_in_rental = hasattr(order, 'rental_start_date')
    
    @api.depends('order_line', 'order_line.is_rental')
    def _compute_is_rental_order(self):
        """Determine if this is a rental order based on order lines."""
        for order in self:
            order.is_rental_order = any(
                line.is_rental for line in order.order_line 
                if hasattr(line, 'is_rental')
            )
    
    @api.depends('order_line', 'order_line.price_subtotal', 'order_line.product_id.recurring_invoice')
    def _compute_recurring_monthly_total(self):
        """Calculate total of ONLY recurring/subscription products."""
        for order in self:
            recurring_lines = order.order_line.filtered(
                lambda line: line.product_id.recurring_invoice
            )
            order.recurring_monthly_total = sum(recurring_lines.mapped('price_subtotal'))
            
            _logger.debug(
                f"Sale Order {order.name}: "
                f"Total lines: {len(order.order_line)}, "
                f"Recurring lines: {len(recurring_lines)}, "
                f"Recurring total: {order.recurring_monthly_total}"
            )
    
    @api.depends('duration_days')
    def _compute_duration_months(self):
        """Convert rental duration from days to months for display."""
        for order in self:
            order.duration_months = int(round(order.duration_days / 30.0)) if order.duration_days else 0

    # ===========================
    # ONCHANGE METHODS
    # ===========================
    
    @api.onchange('order_line')
    def _onchange_rental_prices(self):
        """Auto-update Security Deposit and Advance Rent prices based on Monthly Rental price."""
        if not self.order_line:
            return

        # Find Monthly Rental line by internal reference
        monthly_rental_line = self.order_line.filtered(
            lambda l: l.product_id.default_code == 'MONTHLY_RENTAL'
        )
        if not monthly_rental_line:
            return

        monthly_price = monthly_rental_line[0].price_unit
        
        # Skip if monthly price is 0 or not set
        if not monthly_price or monthly_price <= 0:
            return

        # Update Security Deposit (2x monthly rent)
        security_deposit_lines = self.order_line.filtered(
            lambda l: l.product_id.default_code == 'SECURITY_DEPOSIT'
        )
        for line in security_deposit_lines:
            if line.price_unit != monthly_price * 2:
                line.price_unit = monthly_price * 2
                _logger.info(f"Updated Security Deposit to {line.price_unit}")

        # Update Advance Rent (1x monthly rent)
        advance_rent_lines = self.order_line.filtered(
            lambda l: l.product_id.default_code == 'ADVANCE_RENT'
        )
        for line in advance_rent_lines:
            if line.price_unit != monthly_price:
                line.price_unit = monthly_price
                _logger.info(f"Updated Advance Rent to {line.price_unit}")

    # ===========================
    # ACTION METHODS
    # ===========================
    
    def action_send_for_review(self):
        """Set substate to 'For Review' and email Rental Managers."""
        self.ensure_one()

        # Set substate to "For Review"
        substate = self.env['base.substate'].search([
            ('name', '=', 'For Review'),
            ('model', '=', 'sale.order'),
        ], limit=1)

        if substate:
            self.substate_id = substate.id

        # Load the email template
        template = self.env.ref(
            "property_lmg_custom.mail_template_rental_review_notification",
            raise_if_not_found=False
        )
        if not template:
            raise UserError(_("Email template not found!"))

        # Get all users in the rental manager group
        manager_group = self.env.ref(
            "property_lmg_custom.group_rental_manager",
            raise_if_not_found=False
        )
        if not manager_group:
            raise UserError(_("Rental Manager group not found!"))

        users = manager_group.users
        if not users:
            raise UserError(_("No users found in Rental Manager group!"))

        # Send email to each manager
        for user in users:
            if user.partner_id and user.partner_id.email:
                try:
                    template.with_context(
                        email_to=user.partner_id.email
                    ).send_mail(
                        self.id,
                        force_send=True,
                        email_values={'email_to': user.partner_id.email}
                    )
                except Exception as e:
                    _logger.error(f"Failed to send email to {user.name}: {str(e)}")

        return True
    
    def action_send_proposal(self):
        """Send proposal email with custom rental proposal template."""
        self.ensure_one()

        self.filtered(lambda so: so.state in ('draft', 'sent')).order_line._validate_analytic_distribution()
        lang = self.env.context.get('lang')

        # Get custom rental proposal template
        custom_template = self.env.ref(
            'property_lmg_custom.mail_template_rental_proposal',
            raise_if_not_found=False
        )
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

        # Check document layout configuration
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
    
    def action_download_contract(self):
        """Download contract PDF."""
        self.ensure_one()
        return self.env.ref('property_lmg_custom.action_report_rent_agreement').report_action(self)

    # ===========================
    # REPORT OVERRIDE METHODS
    # ===========================
    
    def _get_default_report_action(self):
        """Override to use custom rental report for rental orders in all states."""
        self.ensure_one()
        
        if self.is_rental_order:
            report = self.env.ref('property_lmg_custom.action_report_rental_quotation')
            _logger.debug(
                f"Using custom rental report for {self.name}: {report.report_name}"
            )
            return report
        
        return super()._get_default_report_action()
    
    def _get_name_portal_content_view(self):
        """Override to use custom portal HTML template for rental orders."""
        self.ensure_one()
        if self.is_rental_order:
            return 'property_lmg_custom.rent_proposal_portal_content'
        return super()._get_name_portal_content_view()

    def _get_report_base_filename(self):
        """Set custom filename for downloaded PDFs."""
        self.ensure_one()
        
        if self.is_rental_order:
            return f'Rental_Proposal_{self.name}'
        
        return super()._get_report_base_filename()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    @api.onchange('price_unit')
    def _onchange_price_unit_rental(self):
        """Trigger parent order's price update when monthly rental price changes."""
        if self.product_id and self.product_id.default_code == 'MONTHLY_RENTAL':
            if self.order_id:
                # Trigger the onchange on the parent order
                self.order_id._onchange_rental_prices()


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'
    
    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """Intercept and redirect rental order reports to use custom rental template."""
        
        # Get the report record
        if isinstance(report_ref, str):
            report = self.env.ref(report_ref, raise_if_not_found=False) or self._get_report(report_ref)
        else:
            report = report_ref
        
        # Check if it's a sale order report
        if report and report.model == 'sale.order' and res_ids:
            orders = self.env['sale.order'].browse(res_ids)
            
            # If ANY order is a rental order, use the custom report
            if any(order.is_rental_order for order in orders):
                rental_report = self.env.ref(
                    'property_lmg_custom.action_report_rental_quotation',
                    raise_if_not_found=False
                )
                
                if rental_report:
                    _logger.info(
                        f"Redirecting to rental report for orders: "
                        f"{', '.join(orders.mapped('name'))}"
                    )
                    # Use the rental report instead
                    return super()._render_qweb_pdf(rental_report, res_ids, data)
        
        return super()._render_qweb_pdf(report_ref, res_ids, data)