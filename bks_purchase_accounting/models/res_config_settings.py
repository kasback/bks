from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bks_fnp_account_id = fields.Many2one(
        related="company_id.bks_fnp_account_id",
        readonly=False,
    )
    bks_fnp_journal_id = fields.Many2one(
        related="company_id.bks_fnp_journal_id",
        readonly=False,
    )
