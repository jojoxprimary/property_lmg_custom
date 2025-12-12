{
    'name': 'Property LMG Rental Substate Custom',
    'version': '1.0',
    'depends': ['sale_renting', 'sale_subscription', 'sale_management', 'base_substate', 'sale_substate', 'stock', 'crm', 'accountant', 'helpdesk'],
    'author': 'Homebrew',
    'category': 'Sales/Rental',
    'data': [
        # Security
        'security/rental_security.xml',
        'security/ir.model.access.csv',

        # Views templates
        'views/rent_proposal_template.xml',
        'views/rent_proposal_portal_template.xml',
        'views/portal_subscription_custom.xml',
        'views/portal_invoice_custom.xml',
        
        # Data & Templates
        'data/mail_template_data.xml',
        'data/mail_template_rent_proposal.xml',
        'data/mail_template_review_notification.xml',

        # Views
        'views/rental_order_view.xml',
    
        # Reports
        'report/rent_agreement_report.xml',
    ],
    'installable': True,
    'application': False,
}
