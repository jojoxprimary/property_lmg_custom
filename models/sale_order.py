from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    substate_id = fields.Many2one('base.substate', string="Substate")
    substate_name = fields.Char(string="Substate Name", compute="_compute_substate_name", store=False)
    payment_attachment = fields.Binary(string="Proposal Payment Attachment")

    is_rental_order = fields.Boolean(
        string="Is Rental Order",
        compute="_compute_is_rental_order",
        store=True
    )

    # OPTION: IS RENTAL ORDER
    @api.depends('order_line', 'order_line.is_rental')
    def _compute_is_rental_order(self):
        for order in self:
            order.is_rental_order = any(line.is_rental for line in order.order_line if hasattr(line, 'is_rental'))

    # TO GET SUBSTATE NAME FOR VIEW PURPOSES
    @api.depends('substate_id')
    def _compute_substate_name(self):
        for order in self:
            order.substate_name = order.substate_id.name or ''

    # SUBMIT FOR REVIEW BUTTON/ACTION -> FROM PROPOSAL TO FOR REVIEW
    def action_send_for_review(self):
        """Set substate to 'For Review' only."""
        substate = self.env['base.substate'].search([
            ('name', '=', 'For Review'), 
            ('model', '=', 'sale.order'),
        ], limit=1)
        if substate:
            self.substate_id = substate.id

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
            # This shows the HTML view in portal "View Details"
            return 'property_lmg_custom.rent_proposal_portal_content'
        return super()._get_name_portal_content_view()

    def _get_report_base_filename(self):
        """Set custom filename for downloaded PDFs"""
        self.ensure_one()
        if self.is_rental_order:
            return 'Rental_Proposal_%s' % (self.name)
        return super()._get_report_base_filename()

    # FROM PROPOSAL SENT TO PROPOSAL SIGNED WHEN CUSTOMER SIGNS
    def _validate_order(self):
        """When customer signs, mark substate as 'Signed' and state in Quotation Sent"""
        for order in self:
            proposal_signed_substate = self.env['base.substate'].search([
                ('name', '=', 'Proposal Signed'),
                ('model', '=', 'sale.order')
            ], limit=1)

            if proposal_signed_substate:
                order.substate_id = proposal_signed_substate.id
                order.message_post(body="Customer signature received. Substate updated to <b>Proposal Signed</b>.")
            else:
                _logger.warning("Substate 'Proposal Signed' not found for sale.order")
    
    # FOR CONFIRM PAYMENT BUTTON/ACTION
    def action_confirm_payment(self):
        self.ensure_one()
        
        # Validations
        if not self.payment_attachment:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Missing Attachment',
                    'message': 'Please upload a payment attachment before confirming payment.',
                    'sticky': False,
                    'type': 'warning',
                }
            }

        if self.substate_name != 'Proposal Signed':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Invalid State',
                    'message': "You can only confirm payment when the substate is 'Proposal Signed'.",
                    'sticky': False,
                    'type': 'danger',
                }
            }
        
        # Find template
        rental_agreement_template = self.env.ref('property_lmg_custom.mail_template_data', raise_if_not_found=False)

        if not rental_agreement_template:
            # Fallback: search by name
            rental_agreement_template = self.env['mail.template'].search([
                ('name', 'ilike', 'rent agreement'),
                ('model', '=', 'sale.order')
            ], limit=1)
        
        # Template check
        if not rental_agreement_template:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Template Missing',
                    'message': "Rental agreement email template not found. Please create it first.",
                    'sticky': False,
                    'type': 'warning',
                }
            }
        
        # Simple context
        lang = self.env.context.get('lang')
        
        ctx = {
            'default_model': 'sale.order',
            'default_res_ids': self.ids,
            'default_composition_mode': 'comment',
            'default_template_id': rental_agreement_template.id,
            'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
            'email_notification_allow_footer': True,
            'force_email': True,
            'model_description': self.with_context(lang=lang).type_name,
            'is_confirm_payment': True,
            'mark_so_as_sent': True,
        }
        
        # Ensure portal token for signature
        self._portal_ensure_token()
        
        # Return email wizard
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }    