# LMG Rental Approval - Agent Context

> **Skill dependency:** Always load `odoo-custom-module-development` before changing this module.

## Project Overview

**Module:** `property_lmg_custom` (Property LMG Rental Substate Custom)
**Version:** `18.0.1.0.0`
**Odoo Version:** `18`
**Dependencies:** `sale`, `sale_renting`, `mail`, `website`, `account`, `crm`
**License:** `LGPL-3`

Custom Odoo module that adds a manager approval workflow for rental quotations, custom rental quotation report routing, rental invoicing periods, and product-level property type classification. Uses native `sale.order.state` with added states — no external substate module dependency.

## Current Directory Structure

```
property_lmg_custom/
├── __manifest__.py
├── __init__.py                         # imports models, controllers
├── Agents.md
├── controllers/
│   ├── __init__.py
│   ├── portal.py                       # rental proposal portal view
│   └── main.py                         # root URL redirect controller
├── data/
│   ├── product.xml                     # rental product data
│   ├── mail_template_rental_approval_request.xml
│   ├── mail_template_rental_rejection.xml
│   ├── mail_template_rental_proposal.xml
│   ├── mail_template_rental_client_approved.xml
│   ├── mail_template_rental_client_thank_you.xml
│   ├── rent_tags.xml                   # rent tag model data
│   └── hand_over_conditions.xml        # hand over conditions data
├── models/
│   ├── __init__.py
│   ├── sale_order_approval.py          # SaleOrder — state extensions, approval workflow, signature handling
│   ├── sale_order_pricing.py           # SaleOrder — duration_months, rental price auto-update, property_unit
│   ├── sale_order_invoicing.py         # SaleOrder — period-based invoicing, pending_count, can_invoice_next_period
│   ├── sale_order_portal_report.py     # SaleOrder — portal views, report filenames, download contract
│   ├── sale_order_line.py              # SaleOrderLine — duration, monthly_price, invoiced_period_ids, _generate_periods
│   ├── report_router.py                # IrActionsReport — redirects rental orders to custom PDF report
│   ├── wizards.py                      # sale.order wizard(s)
│   ├── account_move.py                 # AccountMove — rental invoice display fields
│   ├── rent_tags.py                    # RentTag model
│   ├── rental_invoiced_period.py       # RentalInvoicedPeriod model
│   ├── rental_occupant.py              # RentalOccupant model
│   └── product_template.py             # ProductTemplate — property_type, is_property_unit
├── report/
│   ├── rental_proposal_template.xml    # QWeb report template for rental proposals
│   └── rent_agreement_report.xml       # QWeb rent agreement/contract report
├── security/
│   ├── ir.model.access.csv             # ACLs
│   └── security.xml                    # group_rental_user, group_rental_manager
└── views/
    ├── sale_order_views.xml            # main form + kanban + list customizations, occupant views
    ├── account_move_views.xml          # invoice tree/form rental fields
    ├── product_template_views.xml      # product template: property_type, is_property_unit flags
    ├── rental_proposal_portal.xml      # portal content view for rental proposals
    └── rental_terms_views.xml          # rental terms views
```

## Architecture

### Workflow: Odoo States

This module extends `sale.order.state` with `to_approve` and `sent` values. No separate substate field is used.

```
Draft → [Submit for Review] → To Approve → [Approve → Send Email] → Sent → [Confirm / Sign] → Sale
```

- **Draft** — initial draft; fields are editable
- **To Approve** — pending manager review; form is readonly (enforced at model level via `write()` override for non-managers); Approve/Reject buttons appear for `group_rental_manager`
- **Sent** — quotation sent to client; "Waiting for Client Signature" badge shown
- **Sale** — order confirmed (signed or admin-confirmed)

### Model Files — `sale.order` Extensions

The `sale.order` model is split across multiple files:

#### `models/sale_order_approval.py`

**Fields**
- `state` — selection_add: `to_approve`, `sent`
- `rental_status` — selection_add: `to_approve`, `sent`, `pickup` (Booked), `return` (Occupied), `returned` (Checked Out)
- `submitted_by_id` — Many2one `res.users`; who submitted for approval
- `is_rental_user_only` — computed boolean: user in group_rental_user AND NOT in group_rental_manager
- `is_for_manager_review` — computed boolean: `is_rental_order AND state == 'to_approve'`
- `agent_id` — Many2one `res.partner` (individuals only); Agent field
- `occupant_ids` — One2many `rental.occupant`; persons to occupy
- `effective_occupy_datetime` — readonly datetime
- `effective_checkout_datetime` — readonly datetime

**Key methods**
- `action_submit_for_review()` — sets state to `to_approve`, records submitter, emails all managers
- `action_approve()` — manager-only; opens mail composer with `mark_rental_as_sent: True` context
- `action_reject()` — manager-only; reverts to draft, emails submitter
- `message_post()` — intercepts with `mark_rental_as_sent` context to set state → `sent`
- `write()` — blocks field edits for rental users when state is `to_approve`; handles client signature detection
- `_send_client_approved_email()` — fires internal + client thank-you emails on signature
- `_compute_is_rental_user_only()` / `_compute_is_for_manager_review()` — computed booleans for view visibility
- `get_view()` / `_get_view()` / `get_views()` — strips missing spreadsheet nodes to avoid view errors

#### `models/sale_order_pricing.py`

**Fields**
- `duration_months` — stored/computed float: `duration_days / 30`, rounded to int
- `show_update_duration` — boolean for UI feedback
- `inherit_space` — Selection: `residential` / `commercial`; inherited from property unit product
- `property_unit_product_id` — computed Many2one `product.template`; first line with `is_property_unit=True`
- `property_unit_display_name` — stored/computed char; display name for kanban

**Key methods**
- `_compute_duration_months()` — `duration_days / 30` rounded
- `_compute_property_unit_product_id()` / `_compute_property_unit_display_name()` — derived from order lines
- `_onchange_detect_property_unit()` — auto-adds SECURITY_DEPOSIT, ADVANCE_RENT, CUSA, OTHER_CHARGES lines; sets inherit_space
- `_update_rental_prices()` — sets monthly price on property unit line; Security Deposit = 2× monthly; Advance Rent = 1× monthly
- `_onchange_rental_prices()` — alias for `_update_rental_prices()`
- `_get_monthly_rental_price()` — looks up pricing from product pricings or list price
- `_get_rental_duration_months()` — computes months from rental_start/return dates
- `action_update_rental_prices()` — user-triggered price update with message post

#### `models/sale_order_invoicing.py`

**Fields**
- `pending_count` — computed int; count of uninvoiced periods
- `has_invoiceable_periods` — computed boolean
- `has_non_rental_to_invoice` — computed boolean
- `can_invoice_next_period` — computed boolean

**Key methods**
- `_create_invoices()` — overrides to link invoices to rental periods; sets period labels on invoice lines
- `action_invoice_next_period()` — creates invoice for next pending rental period
- `_get_invoice_period_rental_lines()` — filters order lines with `is_rental` or `rent_ok`

#### `models/sale_order_portal_report.py`

- `_get_name_portal_content_view()` — returns `rental_proposal_portal_content` for rental orders
- `_get_report_base_filename()` — returns `Rental_Proposal_{name}`
- `_get_default_report_action()` — returns `action_report_rental_quotation` for rental orders
- `action_download_contract()` — checks occupants exist, then triggers `action_report_rent_agreement`

#### `models/sale_order_line.py`

**Fields**
- `rental_product_name` — computed char
- `duration` — computed int; months from parent order
- `monthly_price` — monetary field
- `is_property_unit_line` — computed boolean; product has `is_property_unit=True`
- `invoiced_period_ids` — One2many `rental.invoiced.period`
- `invoiced_count` / `pending_count` — computed ints from periods

**Key methods**
- `_generate_periods()` — creates RentalInvoicedPeriod records for each month of rental
- `_link_existing_invoices_to_periods()` — matches existing invoices to periods
- `_get_next_pending_period()` — returns first period without invoice
- `_onchange_price_unit_rental()` — triggers parent order's `_onchange_rental_prices()`
- `_prepare_invoice_line()` — sets period label and quantity=1 for rental invoices

#### `models/report_router.py`

- `_render_qweb_pdf()` — intercepts ALL `sale.order` report rendering; if any order is rental, redirects to `action_report_rental_quotation`

### Other Models

| Model File | Model | Key Content |
|-----------|-------|------------|
| `models/account_move.py` | `account.move` | `is_rental_invoice`, `rental_property_unit_display`, `rental_period_display` computed fields |
| `models/product_template.py` | `product.template` | `property_type` (residential/commercial), `is_property_unit` boolean |
| `models/wizards.py` | wizard(s) | Sale order wizards |
| `models/rental_occupant.py` | `rental.occupant` | surname, first_name, middle_name, date_of_birth, relationship, contact_number; FK to sale.order |
| `models/rental_invoiced_period.py` | `rental.invoiced.period` | period_number, period_start_date, period_end_date, amount, invoice_id; FK to sale.order.line |
| `models/rent_tags.py` | `rent.tag` | Rent tags |

## Security Groups

| XML ID | Name | Implies |
|--------|------|---------|
| `property_lmg_custom.group_rental_user` | Rental User | `base.group_user` |
| `property_lmg_custom.group_rental_manager` | Rental Manager | `property_lmg_custom.group_rental_user` |

Category: `module_category_rental_lmg` (Rental Management LMG)

## View Files

### `views/sale_order_views.xml`
- `view_sale_order_form_custom` — inherits `sale.view_order_form`; adds workflow buttons, agent field, duration_months, readonly controls, occupant tab, effective date fields
- `view_sale_order_form_order_line` — adds rental columns (duration, monthly_price, tax, base, total) to order line list; hides qty/delivered/returned for rental
- `view_sale_order_form_occupants_tab` — Persons to Occupy tab page (visible in sale state)
- `view_rental_order_kanban_custom` — inherits `sale_renting.rental_order_view_kanban`; adds property unit display, relabels dates
- `view_rental_occupant_tree` / `view_rental_occupant_form` — standalone views for rental.occupant model
- `view_rental_order_hide_badges` — hides Booked/Late Pickup badges on rental form
- `view_subscription_quotation_pill` / `view_subscription_state_badge_hide` — subscription view overrides

### `views/account_move_views.xml`
- `view_invoice_tree_rental` — adds property_unit, rental_period columns to invoice tree
- `view_invoice_form_rental` — adds rental-specific columns (tax/base/total) to invoice line list, hides default amount columns

### `views/product_template_views.xml`
- `product_template_form_custom` — adds property_type radio, is_property_unit checkbox to product template form

### `views/rental_proposal_portal.xml`
- Portal content template `rental_proposal_portal_content` for rental proposal display

### `views/rental_terms_views.xml`
- Rental terms views

## Odoo 18 View Rules (CRITICAL)

### NO `attrs` attribute
Since Odoo 17, the `attrs` attribute on `<field>` and `<button>` tags is **removed**. Do not use `attrs="{'readonly': [...], 'invisible': [...]}"`.

**Replacements:**
- **Visibility:** Use `invisible="condition"` directly on the field/button tag
- **Readonly:** Handled at model level via `write()` override (see `sale_order_approval.py`)
- **Column visibility in lists:** Use `column_invisible="condition"` instead of `attrs="{'invisible': [...]}"`

### `<list>` not `<tree>` in one2many fields
Odoo 18 uses `<list>` (not `<tree>`) inside one2many fields in form views. When writing XPath expressions to target the embedded list:
```xml
<!-- CORRECT -->
<xpath expr="//field[@name='order_line']/list" position="inside">
<xpath expr="//field[@name='order_line']/list/field[@name='product_uom_qty']" position="attributes">

<!-- WRONG (will fail to locate element) -->
<xpath expr="//field[@name='order_line']/tree" position="inside">
```

Standalone (root-level) tree/list views still accept `<tree>` for backward compatibility, but `<list>` is preferred.

## Report Routing

1. **`_get_default_report_action()`** on `sale.order` — for backend report links
2. **`_render_qweb_pdf()`** on `ir.actions.report` — intercepts ALL report rendering for `sale.order` model
3. **Portal controller** — for customer portal PDF downloads
4. **`_get_name_portal_content_view()`** — for HTML portal rendering

## Product Data (`data/product.xml`)

| Product | `default_code` | Notes |
|---------|---------------|-------|
| Monthly Rental | `MONTHLY_RENTAL` | `recurring_invoice=True`, service type (deprecated by is_property_unit) |
| Security Deposit | `SECURITY_DEPOSIT` | One-time, auto-priced at 2× monthly |
| Advance Rent | `ADVANCE_RENT` | One-time, auto-priced at 1× monthly |
| CUSA | `CUSA` | Service type (commercial only) |
| Other Charges | `OTHER_CHARGES` | Service type (commercial only) |

Price auto-update: when a property unit product is added to order lines, `_onchange_detect_property_unit()` auto-adds the required products and triggers `_update_rental_prices()`.

## Email Templates

| XML ID | Purpose |
|--------|---------|
| `property_lmg_custom.mail_template_rental_approval_request` | Internal notification to managers when submitted for review |
| `property_lmg_custom.mail_template_rental_rejection` | Notification to submitter when rejected |
| `property_lmg_custom.mail_template_rental_proposal` | Rental proposal sent to customer on approval |
| `property_lmg_custom.mail_template_rental_client_approved` | Internal notification when client signs |
| `property_lmg_custom.mail_template_rental_client_thank_you` | Thank-you email to client after signature |

## Report Templates

| XML ID | Type | Purpose |
|--------|------|---------|
| `property_lmg_custom.action_report_rental_quotation` | QWeb PDF | Rental proposal report |
| `property_lmg_custom.action_report_rent_agreement` | QWeb PDF | Signed rent agreement/contract |

## Development Notes

- Do not run module upgrade automatically (`-u property_lmg_custom`) in agent sessions.
- Keep changes inside this custom module only; never modify `enterprise_addons/`.
- Workflow uses native `sale.order.state` with added values `to_approve`, `sent` (not a separate substate field).
- Product mapping uses `default_code` values: `MONTHLY_RENTAL`, `SECURITY_DEPOSIT`, `ADVANCE_RENT`, `CUSA`, `OTHER_CHARGES`.
- `is_rental_order` comes from `sale_renting` module (computed from order lines' `is_rental` flags).
- **Odoo 18:** No `attrs` on view elements. Use `invisible`, `column_invisible`, and model-level `write()` overrides instead.
- **Odoo 18:** XPath expressions targeting one2many field lists must use `/list`, not `/tree`.

## Git Rules

- This module has its own git repository at `custom_addons/property_lmg_custom/`.
- Run all module git commands from the `property_lmg_custom` directory.
- Never commit secrets, passwords, or `.env` values.
- Never run destructive git commands unless explicitly requested.
