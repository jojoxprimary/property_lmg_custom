{
    'name': 'LMG Rental Approval',
    'version': '18.0.1.0.0',
    'category': 'Sales/Rental',
    'summary': 'Approval workflow for rental quotations',
    'description': """
        Adds a mandatory approval step for rental quotations.
        Rental Users must submit quotations for approval by a Rental Manager
        before they can be sent to the customer.
    """,
    'depends': ['sale', 'sale_renting', 'mail', 'website', 'account', 'crm'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        # 'data/product.xml',
        'report/rental_proposal_template.xml',
        'report/rent_agreement_report.xml',
        'data/mail_template_rental_approval_request.xml',
        'data/mail_template_rental_rejection.xml',
        'data/mail_template_rental_proposal.xml',
        'data/mail_template_rental_client_approved.xml',
        'data/mail_template_rental_client_thank_you.xml',
        'data/rent_tags.xml',
        'data/hand_over_conditions.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'views/product_template_views.xml',
        'views/rental_proposal_portal.xml',
        'views/rental_terms_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
