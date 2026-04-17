---
title: Property LMG Custom Module
created: 2024-01-01
tags: [#odoo #property #rental]
module: property_lmg_custom
status: active
---

# Property LMG Custom Module

Odoo custom module extending `sale_renting` for property rental management.

## Module Info

- **Version:** 1.0 (Odoo 18)
- **Category:** Sales/Rental
- **Dependencies:** `sale_renting`, `sale_subscription`, `sale_management`, `stock`, `crm`, `accountant`, `helpdesk`, `website`, `web_studio`

## Structure

```
property_lmg_custom/
├── models/
│   ├── sale_order.py
│   ├── sale_order_cancel.py
│   ├── rental_substate.py
│   ├── product.py
│   └── crm_lead.py
├── views/
│   ├── rental_order_view.xml
│   ├── crm_lead_view.xml
│   ├── product_view.xml
│   └── ...
├── controllers/
│   ├── main.py
│   ├── portal.py
├── security/
│   └── rental_security.xml
└── report/
    └── rent_agreement_report.xml
```

## Structure

| File | Description |
|------|-------------|
| [[01-models]] | Models, fields, methods |
| [[02-views]] | Views and controllers |
| [[03-data]] | Substates, templates, products |

## Quick Links

- [Models](01-models.md)
- [Views](02-views.md)
- [Data](03-data.md)