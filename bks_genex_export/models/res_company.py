from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    genex_company_code = fields.Integer(
        string="GENEX code entreprise",
        default=1,
        help="Colonne « Code Entreprise » (valeur fixe 1 en général).",
    )
    genex_default_agency_code = fields.Integer(
        string="GENEX code agence par défaut",
        default=1000,
    )
    genex_currency_code = fields.Integer(
        string="GENEX code devise",
        default=504,
        help="504 = dirham marocain.",
    )
    genex_ec_type = fields.Integer(
        string="GENEX type EC Odoo",
        default=563,
        help="Type d'écriture iMal pour les écritures exportées depuis Odoo (563).",
    )
