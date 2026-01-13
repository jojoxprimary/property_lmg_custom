from odoo import http
from odoo.http import request


class WebsiteHomeRedirect(http.Controller):

    @http.route('/', type='http', auth='public', website=True)
    def home_redirect(self, **kw):

        # 🚨 VERY IMPORTANT: let website/editor render normally
        if request.context.get('website_id'):
            return request.env['ir.http']._serve_page()

        user = request.env.user

        if user._is_public():
            return request.redirect('/web/login')

        if user.has_group('base.group_user'):
            return request.redirect('/odoo')

        if user.has_group('base.group_portal'):
            return request.redirect('/my')

        return request.redirect('/web/login')
