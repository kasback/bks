from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    genex_cif = fields.Integer(
        string="GENEX Num CIF",
        help="Identifiant client/fournisseur iMal (0 si non applicable).",
    )
    genex_rib = fields.Char(
        string="GENEX compte RIB",
        size=24,
        help="Compte iMal sur 24 positions.",
    )
