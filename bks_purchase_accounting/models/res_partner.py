from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    property_account_advance_id = fields.Many2one(
        "account.account",
        string="Compte Avance fournisseur",
        company_dependent=True,
        check_company=True,
        ondelete="restrict",
        help="Compte utilisé pour les factures d'avance (acompte) de ce fournisseur.",
    )
    property_account_fnp_id = fields.Many2one(
        "account.account",
        string="Compte FNP fournisseur",
        company_dependent=True,
        check_company=True,
        ondelete="restrict",
        help="Compte FNP utilisé pour les provisions de ce fournisseur "
        "(à défaut, compte FNP de la société).",
    )
