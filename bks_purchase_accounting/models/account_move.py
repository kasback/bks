from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    bks_fnp_reversal_move_id = fields.Many2one(
        "account.move",
        string="Extourne FNP",
        copy=False,
        readonly=True,
    )

    def _post(self, soft=True):
        invoices = self.filtered(
            lambda m: m.is_purchase_document(include_receipts=True)
            and m.state == "draft"
            and not m.bks_fnp_reversal_move_id
        )
        for invoice in invoices:
            reversal = self.env["bks.purchase.fnp"]._reverse_for_invoice(invoice)
            if reversal:
                invoice.bks_fnp_reversal_move_id = reversal.id
        return super()._post(soft)
