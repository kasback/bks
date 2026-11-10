{
    "name": "BKS — Retenues à la source (achats)",
    "version": "19.0.1.0.5",
    "category": "Accounting/Localizations",
    "summary": "RAS achat à la facture (BKS) ; proposition moteur RMG sur les lignes",
    "depends": [
        "rmg_l10n_ma_withholding",
        "bks_purchase_approval",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/account_move_views.xml",
        "views/product_template_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
