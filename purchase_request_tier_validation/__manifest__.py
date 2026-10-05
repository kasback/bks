# Copyright 2019-2020 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Purchase Request Tier Validation",
    "summary": "Extends the functionality of Purchase Requests to "
    "support a tier validation process.",
    "version": "19.0.1.3.1",
    "category": "Purchase Management",
    "website": "https://github.com/OCA/tier-validation",
    "author": "ForgeFlow, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["purchase_request", "base_tier_validation", "hr"],
    "data": [
        "security/purchase_approval_security.xml",
        "security/purchase_request_coordonnateur_rules.xml",
        "security/purchase_request_acheteur_rules.xml",
        "data/tier_definition.xml",
        "views/purchase_request_view.xml",
    ],
    "demo": [
        "demo/tier_definition.xml",
    ],
}
