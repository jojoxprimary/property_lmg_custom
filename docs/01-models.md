---
title: Models Overview
created: 2024-01-01
tags: [#odoo #models]
related: [[00 - Project Overview]]
---

# Models Overview

## Model Files

| File | Extends | Purpose |
|------|---------|---------|
| `sale_order.py` | `sale.order` | Rental order workflow & pricing |
| `sale_order_cancel.py` | `sale.order` | Cancellation handling |
| `rental_substate.py` | `rental.substate` | Custom substates |
| `product.py` | `product.product` | Product extensions |
| `crm_lead.py` | `crm.lead` | Lead customizations |

## SaleOrder Fields

### Status Fields
- `substate_id` → `rental.substate` - Current workflow state
- `rental_substate` - Selection: `Proposal`, `For Review`
- `substate_name` - Computed substate display name

### Computed Fields
- `is_for_manager_review` - True when substate = "For Review" + user in `group_rental_user`
- `is_rental_order` - True if any order line has `is_rental`
- `is_in_rental` - True if rental extension is active

### Financial Fields
- `recurring_monthly_total` - Sum of recurring/subscription products only
- `duration_months` - Duration converted to months (days/30)

## Methods

### Computations
- `_compute_rental_substate()` - Set rental_substate from substate_id
- `_compute_is_for_manager_review()` - Check manager review eligibility
- `_compute_recurring_monthly_total()` - Sum recurring lines only

### Actions
- `action_send_for_review()` - Send to manager with email
- `action_send_proposal()` - Send proposal via email
- `action_download_contract()` - Generate contract PDF

### Onchange
- `_onchange_property_unit()` - Auto-add rental products (MONTHLY_RENTAL, SECURITY_DEPOSIT, ADVANCE_RENT)
- `_onchange_rental_prices()` - Auto-update deposit (2x) and advance (1x) when monthly changes

## Key Business Logic

### Auto-Pricing
```
MONTHLY_RENTAL × 2 = SECURITY_DEPOSIT
MONTHLY_RENTAL × 1 = ADVANCE_RENT
```

### Substate Flow
```
Proposal → For Review → (approved) → Rental Start
```

## Related Notes

- [[00 - Project Overview]]
- [[04 - Business Logic]]