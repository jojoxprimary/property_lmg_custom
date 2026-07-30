from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.addons.sale.tests.common import SaleCommon
from odoo.addons.sale_renting.tests.common import TestRentingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestRentalApprovalWorkflow(SaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.rental_user_group = cls.env.ref('property_lmg_custom.group_rental_user')
        cls.rental_manager_group = cls.env.ref('property_lmg_custom.group_rental_manager')

        cls.rental_user = cls.env['res.users'].create({
            'name': 'Rental User',
            'login': 'rental_user',
            'groups_id': [(6, 0, [cls.rental_user_group.id])],
        })
        cls.rental_manager = cls.env['res.users'].create({
            'name': 'Rental Manager',
            'login': 'rental_manager',
            'groups_id': [(6, 0, [cls.rental_manager_group.id])],
        })

        cls.property_unit = cls.env['product.product'].create({
            'name': 'Test Property Unit A102',
            'type': 'service',
            'rent_ok': True,
            'is_property_unit': True,
            'space_use': 'residential',
            'floor': 5,
            'area': 45.0,
            'list_price': 15000.0,
            'property_type': 'residential',
        })

        cls.monthly_rental_product = cls.env['product.product'].create({
            'name': 'Monthly Rental',
            'default_code': 'MONTHLY_RENTAL',
            'type': 'service',
            'recurring_invoice': True,
        })
        cls.security_deposit_product = cls.env['product.product'].create({
            'name': 'Security Deposit',
            'default_code': 'SECURITY_DEPOSIT',
            'type': 'service',
        })
        cls.advance_rent_product = cls.env['product.product'].create({
            'name': 'Advance Rent',
            'default_code': 'ADVANCE_RENT',
            'type': 'service',
        })

    def _create_rental_order(self, **kwargs):
        start_date = fields.Datetime.now() + timedelta(days=7)
        end_date = start_date + relativedelta(months=6)
        vals = {
            'partner_id': self.partner.id,
            'rental_start_date': kwargs.get('rental_start_date', start_date),
            'rental_return_date': kwargs.get('rental_return_date', end_date),
            'order_line': [
                (0, 0, {
                    'product_id': self.property_unit.id,
                    'product_uom_qty': 6,
                    'price_unit': 15000.0,
                    'is_rental': True,
                }),
                (0, 0, {
                    'product_id': self.monthly_rental_product.id,
                    'product_uom_qty': 6,
                    'price_unit': 15000.0,
                }),
                (0, 0, {
                    'product_id': self.security_deposit_product.id,
                    'product_uom_qty': 1,
                    'price_unit': 30000.0,
                }),
                (0, 0, {
                    'product_id': self.advance_rent_product.id,
                    'product_uom_qty': 1,
                    'price_unit': 15000.0,
                }),
            ],
        }
        vals.update(kwargs)
        order = self.env['sale.order'].with_context(
            default_rental_start_date=vals.get('rental_start_date'),
            default_rental_return_date=vals.get('rental_return_date'),
        ).create(vals)
        return order

    # ========================
    # SUBMISSION TESTS
    # ========================

    def test_01_submit_for_review(self):
        """Rental user can submit a rental quotation for review."""
        order = self._create_rental_order()
        order.with_user(self.rental_user).action_submit_for_review()
        self.assertEqual(order.state, 'to_approve')

    def test_02_submit_non_rental_order(self):
        """Non-rental orders cannot be submitted for review."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.env.ref('product.product_product_27').id,
                    'product_uom_qty': 1,
                }),
            ],
        })
        self.assertFalse(order.is_rental_order)
        with self.assertRaises(UserError):
            order.with_user(self.rental_user).action_submit_for_review()

    # ========================
    # APPROVAL TESTS
    # ========================

    def test_03_manager_approve(self):
        """Rental manager can approve a submitted quotation."""
        order = self._create_rental_order()
        order.with_user(self.rental_user).action_submit_for_review()
        self.assertEqual(order.state, 'to_approve')
        result = order.with_user(self.rental_manager).action_approve()
        self.assertIsNotNone(result)
        self.assertIn('default_template_id', result.get('context', {}))

    def test_04_user_cannot_approve(self):
        """Rental user (non-manager) cannot approve."""
        order = self._create_rental_order()
        order.with_user(self.rental_user).action_submit_for_review()
        with self.assertRaises(UserError):
            order.with_user(self.rental_user).action_approve()

    def test_05_manager_reject(self):
        """Rental manager can reject a submission."""
        order = self._create_rental_order()
        order.with_user(self.rental_user).action_submit_for_review()
        order.with_user(self.rental_manager).action_reject()
        self.assertEqual(order.state, 'draft')

    def test_06_user_cannot_reject(self):
        """Rental user cannot reject."""
        order = self._create_rental_order()
        order.with_user(self.rental_user).action_submit_for_review()
        with self.assertRaises(UserError):
            order.with_user(self.rental_user).action_reject()

    # ========================
    # PRICE UPDATE TESTS
    # ========================

    def test_07_price_update_on_monthly_change(self):
        """Changing monthly rental price updates deposit and advance."""
        order = self._create_rental_order()
        order.order_line.filtered(lambda l: l.product_id.default_code == 'MONTHLY_RENTAL').price_unit = 20000.0
        order._onchange_rental_prices()

        deposit_line = order.order_line.filtered(lambda l: l.product_id.default_code == 'SECURITY_DEPOSIT')
        advance_line = order.order_line.filtered(lambda l: l.product_id.default_code == 'ADVANCE_RENT')

        self.assertEqual(deposit_line.price_unit, 40000.0)
        self.assertEqual(advance_line.price_unit, 20000.0)

    def test_08_duration_computed_from_dates(self):
        """Duration months is computed from rental start/end dates."""
        order = self._create_rental_order()
        self.assertGreater(order.duration_months, 0)

    def test_09_duration_update_on_date_change(self):
        """Changing rental dates updates duration."""
        order = self._create_rental_order()
        old_duration = order.duration_months

        start = fields.Datetime.now() + timedelta(days=7)
        order.rental_start_date = start
        order.rental_return_date = start + relativedelta(months=12)
        self.assertGreater(order.duration_months, old_duration)
        self.assertAlmostEqual(order.duration_months, 12, delta=1)

    # ========================
    # PERIOD GENERATION
    # ========================

    def test_10_invoice_period_generation(self):
        """Periods are generated for property unit lines."""
        order = self._create_rental_order()
        line = order.order_line.filtered('product_id.is_property_unit')
        self.assertTrue(line)
        line._generate_periods()
        self.assertGreater(len(line.invoiced_period_ids), 0)

    # ========================
    # MIXED ORDER TEST
    # ========================

    def test_11_mixed_order_rental_detection(self):
        """Order with rental and non-rental lines is detected as rental."""
        order = self._create_rental_order()
        order.write({
            'order_line': [(0, 0, {
                'product_id': self.env.ref('product.product_product_27').id,
                'product_uom_qty': 1,
            })],
        })
        self.assertTrue(order.is_rental_order)

    # ========================
    # FIELD RESTRICTIONS
    # ========================

    def test_12_blocked_fields_during_approval(self):
        """Rental user cannot modify blocked fields during approval."""
        order = self._create_rental_order()
        order.with_user(self.rental_user).action_submit_for_review()

        with self.assertRaises(UserError):
            order.with_user(self.rental_user).write({'partner_id': self.partner.id})

    def test_13_minimum_rental_duration(self):
        """Rental must be at least 2 months."""
        with self.assertRaises(UserError):
            start = fields.Datetime.now() + timedelta(days=1)
            order = self._create_rental_order(
                rental_start_date=start,
                rental_return_date=start + timedelta(days=30),
            )


@tagged('post_install', '-at_install')
class TestRentalOrderLineFeatures(TestRentingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.property_unit = cls.env['product.product'].create({
            'name': 'Test Unit B201',
            'type': 'service',
            'rent_ok': True,
            'is_property_unit': True,
            'space_use': 'commercial',
            'floor': 3,
            'area': 120.0,
            'list_price': 35000.0,
            'property_type': 'commercial',
        })

        start_date = fields.Datetime.now() + timedelta(days=7)
        end_date = start_date + relativedelta(months=12)

        cls.rental_order = cls.env['sale.order'].create({
            'partner_id': cls.env.ref('base.res_partner_1').id,
            'rental_start_date': start_date,
            'rental_return_date': end_date,
            'order_line': [
                (0, 0, {
                    'product_id': cls.property_unit.id,
                    'product_uom_qty': 12,
                    'price_unit': 35000.0,
                    'is_rental': True,
                }),
            ],
        })

    def test_01_computed_fields(self):
        """Computed fields are populated correctly."""
        order = self.rental_order
        self.assertTrue(order.is_rental_order)
        self.assertGreater(order.duration_months, 0)
        self.assertTrue(order.property_unit_product_id)
        self.assertEqual(order.property_unit_product_id.name, 'Test Unit B201')

    def test_02_period_generation_with_is_property_unit(self):
        """Period generation works with is_property_unit product."""
        line = self.rental_order.order_line.filtered('product_id.is_property_unit')
        self.assertTrue(line)
        line._generate_periods()
        self.assertGreater(len(line.invoiced_period_ids), 0)
        self.assertTrue(all(p.amount == 35000.0 for p in line.invoiced_period_ids))

    def test_03_period_generation_skips_non_property_unit(self):
        """Period generation is skipped for non-property-unit products."""
        non_property_product = self.env['product.product'].create({
            'name': 'Regular Product',
            'type': 'service',
        })
        line = self.rental_order.order_line.create({
            'order_id': self.rental_order.id,
            'product_id': non_property_product.id,
            'product_uom_qty': 1,
        })
        line._generate_periods()
        self.assertEqual(len(line.invoiced_period_ids), 0)

    def test_04_line_invoiced_pending_count(self):
        """Invoiced and pending counts compute correctly."""
        line = self.rental_order.order_line.filtered('product_id.is_property_unit')
        line._generate_periods()
        self.assertEqual(line.invoiced_count, 0)
        self.assertEqual(line.pending_count, len(line.invoiced_period_ids))

    def test_05_duration_computed_on_line(self):
        """Duration is computed on order lines."""
        line = self.rental_order.order_line.filtered('product_id.is_property_unit')
        self.assertGreater(int(line.duration), 0)


@tagged('post_install', '-at_install')
class TestRentalPortalFeatures(SaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.property_unit = cls.env['product.product'].create({
            'name': 'Portal Test Unit C303',
            'type': 'service',
            'rent_ok': True,
            'is_property_unit': True,
            'space_use': 'residential',
            'list_price': 20000.0,
        })

        start_date = fields.Datetime.now() + timedelta(days=14)
        end_date = start_date + relativedelta(months=6)

        cls.rental_order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'rental_start_date': start_date,
            'rental_return_date': end_date,
            'order_line': [
                (0, 0, {
                    'product_id': cls.property_unit.id,
                    'product_uom_qty': 6,
                    'price_unit': 20000.0,
                    'is_rental': True,
                }),
            ],
        })

    def test_01_portal_view_content(self):
        """Rental order returns custom portal content view."""
        view = self.rental_order._get_name_portal_content_view()
        self.assertEqual(view, 'property_lmg_custom.rental_proposal_portal_content')

    def test_02_non_rental_uses_default_view(self):
        """Non-rental order returns default portal content view."""
        non_rental = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.env.ref('product.product_product_27').id,
                    'product_uom_qty': 1,
                }),
            ],
        })
        view = non_rental._get_name_portal_content_view()
        self.assertNotEqual(view, 'property_lmg_custom.rental_proposal_portal_content')

    def test_03_report_filename(self):
        """Rental order report filename uses custom naming."""
        filename = self.rental_order._get_report_base_filename()
        self.assertIn('Rental_Proposal_', filename)
        self.assertIn(self.rental_order.name, filename)

    def test_04_non_rental_report_filename(self):
        """Non-rental order uses default filename."""
        non_rental = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'name': 'S00042',
            'order_line': [
                (0, 0, {
                    'product_id': self.env.ref('product.product_product_27').id,
                    'product_uom_qty': 1,
                }),
            ],
        })
        filename = non_rental._get_report_base_filename()
        self.assertNotIn('Rental_Proposal_', filename)

    def test_05_default_report_action(self):
        """Rental order returns custom report action."""
        report = self.rental_order._get_default_report_action()
        self.assertEqual(report.report_name, 'property_lmg_custom.report_rental_quotation_document')


@tagged('post_install', '-at_install')
class TestRentalSecurity(TestRentingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.rental_user_group = cls.env.ref('property_lmg_custom.group_rental_user')
        cls.rental_manager_group = cls.env.ref('property_lmg_custom.group_rental_manager')

        cls.rental_user = cls.env['res.users'].create({
            'name': 'Sec Rental User',
            'login': 'sec_rental_user',
            'groups_id': [(6, 0, [cls.rental_user_group.id])],
        })
        cls.rental_manager = cls.env['res.users'].create({
            'name': 'Sec Rental Manager',
            'login': 'sec_rental_manager',
            'groups_id': [(6, 0, [cls.rental_manager_group.id])],
        })

        cls.property_unit = cls.env['product.product'].create({
            'name': 'Security Test Unit',
            'type': 'service',
            'rent_ok': True,
            'is_property_unit': True,
            'list_price': 10000.0,
        })

    def _create_security_rental_order(self):
        return self.env['sale.order'].create({
            'partner_id': self.env.ref('base.res_partner_1').id,
            'rental_start_date': fields.Datetime.now() + timedelta(days=7),
            'rental_return_date': fields.Datetime.now() + timedelta(days=37),
            'order_line': [
                (0, 0, {
                    'product_id': self.property_unit.id,
                    'product_uom_qty': 1,
                    'price_unit': 10000.0,
                    'is_rental': True,
                }),
            ],
        })

    def test_01_rental_user_has_group(self):
        """Rental user is in the rental user group."""
        self.assertTrue(self.rental_user.has_group('property_lmg_custom.group_rental_user'))

    def test_02_rental_manager_has_manager_group(self):
        """Rental manager is in the rental manager group."""
        self.assertTrue(self.rental_manager.has_group('property_lmg_custom.group_rental_manager'))

    def test_03_manager_implies_user(self):
        """Rental manager group implies rental user group."""
        self.assertTrue(self.rental_manager.has_group('property_lmg_custom.group_rental_user'))

    def test_04_group_hierarchy(self):
        """Rental user group is a subgroup of rental manager group."""
        implied = self.rental_manager_group.implied_ids
        self.assertIn(self.rental_user_group, implied)

    def test_05_user_can_submit(self):
        """Rental user can submit for review."""
        order = self._create_security_rental_order()
        order.with_user(self.rental_user).action_submit_for_review()
        self.assertEqual(order.state, 'to_approve')

    def test_06_non_user_cannot_submit(self):
        """Users without rental permissions cannot submit."""
        order = self._create_security_rental_order()
        plain_user = self.env.ref('base.user_demo')
        with self.assertRaises(UserError):
            order.with_user(plain_user).action_submit_for_review()

    def test_07_property_unit_required(self):
        """Rental orders require a property unit product."""
        order = self.env['sale.order'].create({
            'partner_id': self.env.ref('base.res_partner_1').id,
            'rental_start_date': fields.Datetime.now() + timedelta(days=7),
            'rental_return_date': fields.Datetime.now() + relativedelta(months=3),
            'order_line': [
                (0, 0, {
                    'product_id': self.env.ref('product.product_product_27').id,
                    'product_uom_qty': 10,
                }),
            ],
        })
        self.assertFalse(order.is_rental_order)
