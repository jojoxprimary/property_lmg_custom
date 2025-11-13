from odoo import http
from odoo.http import request
from odoo.addons.sale.controllers.portal import CustomerPortal


class RentalCustomerPortal(CustomerPortal):

    @http.route(['/my/orders/<int:order_id>'], type='http', auth="public", website=True)
    def portal_order_page(self, order_id, access_token=None, report_type=None, download=False, **kw):
        """Override to use custom PDF for rental orders"""
        try:
            order_sudo = self._document_check_access('sale.order', order_id, access_token=access_token)
        except Exception:
            return request.redirect('/my')

        # If requesting PDF and it's a rental order
        if report_type == 'pdf' and order_sudo.is_rental_order:
            # Use custom rental report
            pdf_report = request.env.ref('property_lmg_custom.action_report_rental_quotation', raise_if_not_found=False)
            
            if pdf_report:
                pdf_content, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
                    pdf_report.report_name,
                    [order_sudo.id]
                )
                
                filename = 'Rental_Proposal_%s.pdf' % order_sudo.name
                
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

        # Otherwise, use default behavior
        return super().portal_order_page(
            order_id=order_id,
            access_token=access_token,
            report_type=report_type,
            download=download,
            **kw
        )