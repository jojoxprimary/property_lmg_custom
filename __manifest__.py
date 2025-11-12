{
    'name': 'Property LMG Rental Substate Custom',
    'version': '1.0',
    'depends': ['sale_renting', 'sale_subscription', 'base_substate'],
    'author': 'Homebrew',
    'category': 'Sales/Rental',
    'data': [
        'data/mail_template_data.xml',  
        'views/rent_proposal_template.xml',
        'data/mail_template_rent_proposal.xml',  
        'views/rental_order_view.xml',
    ],
    'installable': True,
    'application': False,
}
