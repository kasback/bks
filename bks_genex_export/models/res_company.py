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
    genex_vdm_bank_code = fields.Integer(
        string="VDM code banque remettant",
        default=362,
    )
    genex_vdm_agency_code = fields.Char(
        string="VDM agence remettant",
        default="1000",
    )
    genex_vdm_remitter_rib = fields.Char(
        string="VDM RIB remettant (24 car.)",
        default="362780936990800064357274",
    )
    genex_vdm_rib_key = fields.Char(
        string="VDM clé RIB remettant",
        default="74",
    )
    genex_vdm_convention_ref = fields.Char(
        string="VDM référence convention Adria",
        default="0000907",
    )
    genex_ov_debit_rib_display = fields.Char(
        string="OV RIB compte à débiter (affichage)",
        default="362 780 93 6990 8 000 643 572 74",
    )
