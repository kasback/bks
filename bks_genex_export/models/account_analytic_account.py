from odoo import fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    genex_agency_code = fields.Integer(
        string="GENEX code agence",
        help="Code agence iMal pour les lignes avec cette analytique.",
    )
