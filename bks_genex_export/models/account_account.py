from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    genex_gl_code = fields.Char(
        string="GENEX code GL",
        size=6,
        help="Compte GL iMal (6 chiffres). Laisser vide pour dériver du numéro de compte.",
    )
