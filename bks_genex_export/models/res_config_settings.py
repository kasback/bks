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
    genex_vdm_bank_code = fields.Integer(
        related="company_id.genex_vdm_bank_code",
        readonly=False,
    )
    genex_vdm_agency_code = fields.Char(
        related="company_id.genex_vdm_agency_code",
        readonly=False,
    )
    genex_vdm_remitter_rib = fields.Char(
        related="company_id.genex_vdm_remitter_rib",
        readonly=False,
    )
    genex_vdm_rib_key = fields.Char(
        related="company_id.genex_vdm_rib_key",
        readonly=False,
    )
    genex_vdm_convention_ref = fields.Char(
        related="company_id.genex_vdm_convention_ref",
        readonly=False,
    )
    genex_ov_debit_rib_display = fields.Char(
        related="company_id.genex_ov_debit_rib_display",
        readonly=False,
    )
