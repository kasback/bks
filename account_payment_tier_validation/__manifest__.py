# Copyright 2025 Spearhead - Ricardo Jara
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Payment Tier Validation",
    "summary": "Extends the functionality of Payment to "
    "support a tier validation process.",
    "version": "19.0.1.0.12",
    "category": "Accounting/Accounting",
    "website": "https://github.com/OCA/tier-validation",
    "author": "Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["account", "base_tier_validation"],
    "data": [
        "security/payment_settlement_security.xml",
        "security/ir.model.access.csv",
        "data/tier_definition.xml",
        "wizard/bks_payment_validate_wizard_views.xml",
        "views/account_payment_register_views.xml",
        "views/account_payment_view.xml",
    ],
}
