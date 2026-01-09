from odoo import http
from odoo.http import request


class WebsiteHomeRedirect(http.Controller):

    @http.route('/', type='http', auth='public', website=True)
    def home_redirect(self, **kw):
        user = request.env.user

        # Public user → let Odoo handle it (login / website)
        if user._is_public():
            return request.redirect('/web/login')

        # Internal users (employees, admins)
        if user.has_group('base.group_user'):
            return request.redirect('/odoo')

        # Portal users
        if user.has_group('base.group_portal'):
            return request.redirect('/my')

        # Fallback
        return request.redirect('/web/login')
