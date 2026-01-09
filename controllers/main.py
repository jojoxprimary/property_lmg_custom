from odoo import http
from odoo.http import request

class WebsiteHomeRedirect(http.Controller):

    @http.route('/', type='http', auth='public', website=True)
    def home_redirect(self, **kw):
        return request.redirect('/my')
