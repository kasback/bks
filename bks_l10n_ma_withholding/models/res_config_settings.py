from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bks_l10n_ma_withholding_on_invoice = fields.Boolean(
        related="company_id.bks_l10n_ma_withholding_on_invoice",
        readonly=False,
    )
