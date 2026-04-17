---
title: Data & Templates
created: 2024-01-01
tags: [#odoo #data #templates]
related: [[00 - Project Overview]], [[01 - Models Overview]]
---

# Data & Templates

## Substates

| ID | Name | Sequence | Default |
|---|---|---|---|
| `substate_proposal` | Proposal | 10 | ✓ |
| `substate_for_review` | For Review | 20 | |
| `substate_proposal_sent` | Proposal Sent | 30 | |
| `substate_agreement_sent` | Rental Agreement Sent | 40 | |
| `substate_confirmed` | Confirmed | 50 | |
| `substate_in_progress` | In Progress | 60 | |
| `substate_completed` | Completed | 70 | |
| `substate_cancelled` | Cancelled | 80 | |

## Substate Flow
```
Proposal → For Review → Proposal Sent → Rental Agreement Sent → Confirmed → In Progress → Completed
                                    → Cancelled
```

## Email Templates

- `mail_template_rental_proposal` - Send proposal to client
- `mail_template_rental_review_notification` - Notify managers
- `mail_template_review_notification` - General review
- `mail_template_cancellation` - Cancellation notice

## Rental Products

| Code | Name | Type |
|---|---|---|
| `MONTHLY_RENTAL` | Monthly Rental | Recurring |
| `SECURITY_DEPOSIT` | Security Deposit | One-time |
| `ADVANCE_RENT` | Advance Rent | One-time |

## Security

- `rental_security.xml` - Access control list
- `ir.model.access.csv` - Model permissions

## Related Notes

- [[00 - Project Overview]]
- [[02 - Views & Controllers]]