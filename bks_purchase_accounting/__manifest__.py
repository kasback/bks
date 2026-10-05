{
    "name": "BKS Purchase Accounting (FNP)",
    "version": "19.0.1.0.4",
    "category": "Accounting/Purchase",
    "summary": "Factures non parvenues achats à la réception et extourne à la facturation",
    "depends": ["purchase_stock", "account"],
    "data": [
        "data/ir_sequence_data.xml",
        "security/ir.model.access.csv",
        "views/bks_purchase_fnp_views.xml",
        "views/res_config_settings_views.xml",
        "views/purchase_order_views.xml",
        "views/stock_picking_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
