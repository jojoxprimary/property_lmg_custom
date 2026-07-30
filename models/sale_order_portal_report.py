import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_name_portal_content_view(self):
        self.ensure_one()
        if self.is_rental_order:
            return 'property_lmg_custom.rental_proposal_portal_content'
        return super()._get_name_portal_content_view()

    def _get_report_base_filename(self):
        self.ensure_one()
        if self.is_rental_order:
            return f'Rental_Proposal_{self.name}'
        return super()._get_report_base_filename()

    def _get_default_report_action(self):
        self.ensure_one()
        if self.is_rental_order:
            report = self.env.ref('property_lmg_custom.action_report_rental_quotation')
            _logger.debug("Using custom rental report for %s: %s", self.name, report.report_name)
            return report
        return super()._get_default_report_action()

    def action_download_contract(self):
        self.ensure_one()
        if not self.occupant_ids:
            raise UserError(_("Please add at least one occupant in the 'Person to Occupy' tab before downloading the contract."))
        return self.env.ref('property_lmg_custom.action_report_rent_agreement').report_action(self)
