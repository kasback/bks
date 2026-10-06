from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    genex_company_code = fields.Integer(
        related="company_id.genex_company_code",
        readonly=False,
    )
    genex_default_agency_code = fields.Integer(
        related="company_id.genex_default_agency_code",
        readonly=False,
    )
    genex_currency_code = fields.Integer(
        related="company_id.genex_currency_code",
        readonly=False,
    )
    genex_ec_type = fields.Integer(related="company_id.genex_ec_type", readonly=False)
