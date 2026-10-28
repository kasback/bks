{
    "name": "BKS — Retenues à la source (achats)",
    "version": "19.0.1.0.2",
    "category": "Accounting/Localizations",
    "summary": "TVA seule sur les articles ; RAS proposée par le moteur RMG sur les factures",
    "depends": [
        "rmg_l10n_ma_withholding",
        "bks_purchase_approval",
    ],
    "data": [
        "views/account_move_views.xml",
        "views/product_template_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
