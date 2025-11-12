{
    'name': 'Property LMG Rental Substate Custom',
    'version': '1.0',
    'depends': ['sale_renting', 'sale_subscription', 'base_substate'],
    'author': 'Homebrew',
    'category': 'Sales/Rental',
    'data': [
        # 1️⃣ Report XML first, so the report action exists
        'report/report_property_quotation_custom.xml',

        # 2️⃣ Mail templates that reference the report
        'data/mail_template_data.xml',
        'data/mail_template_rent_proposal.xml',

        # 3️⃣ Views last
        'views/rent_proposal_template.xml',
        'views/rental_order_view.xml',
    ],
    'installable': True,
    'application': False,
}
