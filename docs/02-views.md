---
title: Views & Controllers
created: 2024-01-01
tags: [#odoo #views #controllers]
related: [[00 - Project Overview]], [[01 - Models Overview]]
---

# Views & Controllers

## Controllers

### `main.py`
- `WebsiteHomeRedirect` - Root redirect based on user type
  - Public → `/web/login`
  - Internal user → `/odoo`
  - Portal user → `/my`

### `portal.py`
Portal-specific endpoints for rental access

## Views (XML)

| File | Purpose |
|------|---------|
| `rental_order_view.xml` | Sale order form/list views |
| `crm_lead_view.xml` | Lead customizations |
| `product_view.xml` | Product extensions |
| `rental_order_kanban.php` | Kanban board view |
| `rent_proposal_template.php` | Proposal email template |
| `rent_proposal_portal_template.php` | Portal proposal view |
| `portal_subscription_custom.php` | Portal subscription |
| `portal_invoice_custom.php` | Portal invoice |

## Related Notes

- [[00 - Project Overview]]
- [[01 - Models Overview]]
- [[03 - Data & Templates]]