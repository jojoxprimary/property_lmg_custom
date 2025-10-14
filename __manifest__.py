{
    'name': 'Property LMG Customization',
    'version': '1.0',
    'summary': 'Custom lease proposal workflow for properties',
    'description': """
        - Adds new states to Sale Orders for Lease Proposals
        - Submit to Supervisor > Approve > Send to Tenant
    """,
    'author': 'HomeBrew',
    'depends': ['sale'],
    'data': [
        'views/sale_order_form_custom.xml',
    ],
    'installable': True,
    'application': False,
}
