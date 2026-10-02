{
    "name": "BKS Circuit validation DA / BDC",
    "summary": "Circuit de validation des demandes d'achat et bons de commande "
    "selon les seuils 40 KDH / 700 KDH.",
    "version": "19.0.1.1.8",
    "category": "Purchases",
    "author": "BKS",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "purchase_request_tier_validation",
        "purchase_tier_validation",
        "hr",
    ],
    "auto_install": True,
    "data": [
        "security/purchase_order_department_rules.xml",
        "views/purchase_request_view.xml",
        "views/tier_validation_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bks_purchase_approval/static/src/js/tier_review_widget_patch.esm.js",
            "bks_purchase_approval/static/src/xml/tier_review_widget.xml",
        ],
    },
}
