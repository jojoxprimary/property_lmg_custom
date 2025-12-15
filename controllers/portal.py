from odoo import http
from odoo.http import request
from odoo.addons.sale.controllers.portal import CustomerPortal


class RentalCustomerPortal(CustomerPortal):

    @http.route(['/my/orders/<int:order_id>'], type='http', auth="public", website=True)
    def portal_order_page(self, order_id, access_token=None, report_type=None, download=False, **kw):
        """Override to use custom PDF report for rental orders"""
        
        # Check access to the order
        try:
            order_sudo = self._document_check_access('sale.order', order_id, access_token=access_token)
        except Exception:
            return request.redirect('/my')

        # Use custom rental report for orders created in rental app
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

        # Use default portal behavior for non-rental orders
        return super().portal_order_page(
            order_id=order_id,
            access_token=access_token,
            report_type=report_type,
            download=download,
            **kw
        )