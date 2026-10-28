from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    bks_guarantee_move_id = fields.Many2one(
        "account.move",
        string="Facture de la retenue de garantie",
        copy=False,
        readonly=True,
        help="Facture fournisseur dont ce règlement libère la retenue de garantie.",
    )

    @api.depends(
        "journal_id",
        "partner_id",
        "partner_type",
        "bks_guarantee_move_id",
        "company_id",
    )
    def _compute_destination_account_id(self):
        super()._compute_destination_account_id()
        for pay in self.filtered("bks_guarantee_move_id"):
            account = pay.bks_guarantee_move_id._bks_guarantee_account()
            if account:
                pay.destination_account_id = account

    def action_open_bks_guarantee_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Facture",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.bks_guarantee_move_id.id,
            "target": "current",
        }
