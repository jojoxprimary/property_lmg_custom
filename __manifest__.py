{
    'name': 'Property LMG Rental Substate Custom',
    'version': '1.0',
    'depends': ['sale_renting', 'base_substate'],
    'author': 'Homebrew',
    'category': 'Sales/Rental',
    'data': [
        'data/mail_template_data.xml',  # Add this line
        'views/rental_order_view.xml',
    ],
    'installable': True,
    'application': False,
}
