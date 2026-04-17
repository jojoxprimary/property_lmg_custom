from odoo import http, fields, _
from odoo.http import request
from odoo.addons.sale.controllers.portal import CustomerPortal


class RentalCustomerPortal(CustomerPortal):

    @http.route(['/my/orders/<int:order_id>'], type='http', auth="public", website=True)
    def portal_order_page(
        self,
        order_id,
        access_token=None,
        report_type=None,
        download=False,
        downpayment=None,
        message=False,
        **kw
    ):
        """Override to use custom portal template for rental orders"""
        try:
            order_sudo = self._document_check_access('sale.order', order_id, access_token=access_token)
        except Exception:
            return request.redirect('/my')

        # Use custom PDF report for rental orders
        if report_type == 'pdf' and order_sudo.is_rental_order:
            # Use sudo() to bypass permission checks for the report
            pdf_report = request.env.ref('property_lmg_custom.action_report_rental_quotation', raise_if_not_found=False).sudo()
            
            if pdf_report:
                # Generate PDF content using sudo() to bypass access rights
                pdf_content, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
                    pdf_report.report_name,
                    [order_sudo.id]
                )
                
                # Set filename
                filename = 'Rental_Proposal_%s.pdf' % order_sudo.name
                
                # Set headers for download or inline display
                if download:
                    pdfhttpheaders = [
                        ('Content-Type', 'application/pdf'),
                        ('Content-Length', len(pdf_content)),
                        ('Content-Disposition', 'attachment; filename=%s' % filename)
                    ]
                else:
                    pdfhttpheaders = [
                        ('Content-Type', 'application/pdf'),
                        ('Content-Length', len(pdf_content)),
                        ('Content-Disposition', 'inline; filename=%s' % filename)
                    ]
                
                return request.make_response(pdf_content, headers=pdfhttpheaders)

        # For HTML display on non-PDF report type, use custom portal template for rental orders
        if order_sudo.is_rental_order:
            return self._render_rental_portal_page(order_sudo, access_token, **kw)

        # Use default portal behavior for non-rental orders
        return super().portal_order_page(
            order_id=order_id,
            access_token=access_token,
            report_type=report_type,
            download=download,
            downpayment=downpayment,
            message=message,
            **kw
        )

    def _render_rental_portal_page(self, order_sudo, access_token=None, message=False, downpayment=None, **kw):
        """Render custom portal template for rental orders"""
        is_link_preview = request.httprequest.headers.get('Odoo-Link-Preview')
        if request.env.user.share and access_token and is_link_preview != 'True':
            today = fields.Date.today().isoformat()
            session_obj_date = request.session.get('view_quote_%s' % order_sudo.id)
            if session_obj_date != today:
                request.session['view_quote_%s' % order_sudo.id] = today
                author = order_sudo.partner_id if request.env.user._is_public() else request.env.user.partner_id
                order_sudo.message_post(
                    author_id=author.id,
                    body=_('Quotation viewed by customer %s', author.name),
                    message_type="notification",
                    subtype_xmlid="sale.mt_order_viewed",
                )

        backend_url = '/odoo/action-%s/%s' % (order_sudo._get_portal_return_action().id, order_sudo.id)
        values = {
            'sale_order': order_sudo,
            'product_documents': order_sudo._get_product_documents(),
            'message': message,
            'report_type': 'html',
            'backend_url': backend_url,
            'res_company': order_sudo.company_id,
        }

        if order_sudo._has_to_be_paid():
            values.update(
                self._get_payment_values(
                    order_sudo,
                    downpayment=downpayment == 'true' if downpayment is not None else order_sudo.prepayment_percent < 1.0
                )
            )

        if order_sudo.state in ('draft', 'sent', 'cancel'):
            history_session_key = 'my_quotations_history'
        else:
            history_session_key = 'my_orders_history'

        values = self._get_page_view_values(
            order_sudo, access_token, values, history_session_key, False, **kw)

        return request.render('property_lmg_custom.rent_proposal_portal_content', values)