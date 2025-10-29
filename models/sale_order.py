from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    substate_id = fields.Many2one('base.substate', string="Substate")
    substate_name = fields.Char(string="Substate Name", compute="_compute_substate_name", store=False)
    payment_attachment = fields.Binary(string="Payment Attachment")

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

    # SEND PROPOSAL BUTTON/ACTION -> FROM FOR REVIEW TO WAITING FOR SIGNATURE
    def action_send_proposal(self):
        """Send proposal email (same as Send by Email) but stay in Quotation and set substate to Waiting for Signature."""
        self.ensure_one()

        self.filtered(lambda so: so.state in ('draft', 'sent')).order_line._validate_analytic_distribution()
        lang = self.env.context.get('lang')

        ctx = {
            'default_model': 'sale.order',
            'default_res_ids': self.ids,
            'default_composition_mode': 'comment',
            'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
            'email_notification_allow_footer': True,
            'proforma': self.env.context.get('proforma', False),
        }

        if len(self) > 1:
            ctx['default_composition_mode'] = 'mass_mail'
        else:
            ctx.update({
                'force_email': True,
                'model_description': self.with_context(lang=lang).type_name,
            })
            if not self.env.context.get('hide_default_template'):
                mail_template = self._find_mail_template()
                if mail_template:
                    ctx.update({
                        'default_template_id': mail_template.id,
                        'mark_so_as_sent': False,  # Keep state as Quotation, True in enterprise
                    })
                if mail_template and mail_template.lang:
                    lang = mail_template._render_lang(self.ids)[self.id]
            else:
                for order in self:
                    order._portal_ensure_token()

        waiting_substate = self.env['base.substate'].search([
            ('name', '=', 'Waiting for Signature'),
            ('model', '=', 'sale.order')
        ], limit=1)
        if waiting_substate:
            self.substate_id = waiting_substate.id
        else:
            raise UserError("Substate 'Waiting for Signature' not found. Please configure it in Base Substates.")

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

    # FROM WAITING FOR SIGNATURE TO SIGNED ON CUSTOMER SIGNATURE
    def _validate_order(self):
        """When customer signs, mark substate as 'Signed' but keep in Quotation."""
        for order in self:
            signed_substate = self.env['base.substate'].search([
                ('name', '=', 'Signed'),
                ('model', '=', 'sale.order')
            ], limit=1)

            if signed_substate:
                order.substate_id = signed_substate.id
                order.message_post(body="✅ Customer signature received. Substate updated to <b>Signed</b>.")
            else:
                _logger.warning("Substate 'Signed' not found for sale.order")

            if order.state != 'draft':
                order.state = 'draft'

    
    # FOR CONFIRM PAYMENT BUTTON/ACTION -> FROM SIGNED TO PAYMENT CONFIRMED
    def action_confirm_payment(self):
        for order in self:
            if not order.payment_attachment:
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

            if order.substate_name != 'Signed':
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Invalid State',
                        'message': "You can only confirm payment when the substate is 'Signed'.",
                        'sticky': False,
                        'type': 'danger',
                    }
                }

            payment_confirmed_substate = self.env['base.substate'].search([
                ('name', '=', 'Payment Confirmed'),
                ('model', '=', 'sale.order')
            ], limit=1)

            if not payment_confirmed_substate:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Substate Missing',
                        'message': "Couldn't find substate 'Payment Confirmed'.",
                        'sticky': False,
                        'type': 'warning',
                    }
                }
            # update substate to Payment Confirmed
            order.substate_id = payment_confirmed_substate.id