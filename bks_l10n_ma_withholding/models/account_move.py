from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.depends("invoice_line_ids.rmg_withholding_proposal_ids")
    def _compute_rmg_has_withholding(self):
        for move in self:
            move.rmg_has_withholding = bool(
                move.invoice_line_ids.mapped("rmg_withholding_proposal_ids")
            )

    @api.depends(
        "invoice_line_ids.rmg_withholding_proposal_ids",
        "invoice_line_ids.price_subtotal",
        "invoice_line_ids.tax_ids",
    )
    def _compute_rmg_withholding_total(self):
        for move in self:
            currency = move.currency_id or move.company_id.currency_id
            total = 0.0
            for line in move.invoice_line_ids.filtered(
                lambda line: line.display_type == "product"
            ):
                total += sum(line._rmg_withholding_by_tax().values())
            move.rmg_withholding_total = currency.round(total)

    @api.onchange("partner_id", "invoice_date", "invoice_line_ids", "fiscal_position_id")
    def _onchange_bks_sync_invoice_withholding(self):
        self.invoice_line_ids._bks_sync_withholding_taxes()
