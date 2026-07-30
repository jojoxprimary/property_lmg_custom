import logging

from odoo import models

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        if isinstance(report_ref, str):
            report = self.env.ref(report_ref, raise_if_not_found=False) or self._get_report(report_ref)
        else:
            report = report_ref

        if report and report.model == 'sale.order' and res_ids:
            orders = self.env['sale.order'].browse(res_ids)

            if any(order.is_rental_order for order in orders):
                rental_report = self.env.ref(
                    'property_lmg_custom.action_report_rental_quotation',
                    raise_if_not_found=False,
                )

                if rental_report:
                    _logger.info(
                        "Redirecting to property_lmg_custom report for orders: %s",
                        ', '.join(orders.mapped('name')),
                    )
                    return super()._render_qweb_pdf(rental_report, res_ids, data)

        return super()._render_qweb_pdf(report_ref, res_ids, data)
