from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    bks_fnp_account_id = fields.Many2one(
        "account.account",
        string="Compte FNP achats",
        domain="[('company_ids', 'in', id)]",
        help="Compte de passif pour les factures non parvenues (ex. 367101).",
    )
    bks_fnp_journal_id = fields.Many2one(
        "account.journal",
        string="Journal FNP achats",
        domain="[('company_id', '=', id), ('type', '=', 'general')]",
        help="Journal des écritures de provision et d'extourne FNP.",
    )
