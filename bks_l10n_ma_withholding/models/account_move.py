from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _bks_withholding_on_invoice_enabled(self):
        self.ensure_one()
        return (
            self.company_id.bks_l10n_ma_withholding_on_invoice
            and self.is_purchase_document(include_receipts=True)
        )

    def _prepare_product_base_line_for_taxes_computation(self, product_line):
        base_line = super()._prepare_product_base_line_for_taxes_computation(product_line)
        if self._bks_withholding_on_invoice_enabled():
            base_line["calculate_withholding_taxes"] = True
            base_line["filter_tax_function"] = None
        return base_line

    def _rmg_measured_withholding(self):
        self.ensure_one()
        if self._bks_withholding_on_invoice_enabled():
            currency = self.currency_id or self.company_id.currency_id
            wh_lines = self.line_ids.filtered(
                lambda line: line.tax_line_id.is_withholding_tax_on_payment
            )
            return currency.round(sum(abs(line.amount_currency) for line in wh_lines))
        return super()._rmg_measured_withholding()

    @api.depends(
        "amount_total",
        "amount_residual",
        "rmg_withholding_total",
        "state",
        "invoice_line_ids.price_total",
        "company_id.bks_l10n_ma_withholding_on_invoice",
    )
    def _compute_rmg_withholding_remaining(self):
        bks_moves = self.filtered(
            lambda move: move._bks_withholding_on_invoice_enabled() and move.rmg_has_withholding
        )
        super(AccountMove, self - bks_moves)._compute_rmg_withholding_remaining()
        for move in bks_moves:
            if move.state == "posted":
                due = move.amount_residual
            else:
                due = move.amount_total or sum(move.invoice_line_ids.mapped("price_total"))
            move.rmg_withholding_remaining = 0.0
            move.rmg_withholding_net_due = due

    @api.depends(
        "line_ids.matched_debit_ids",
        "line_ids.matched_credit_ids",
        "amount_residual",
        "amount_total",
        "rmg_withholding_total",
        "state",
        "line_ids.tax_line_id",
        "company_id.bks_l10n_ma_withholding_on_invoice",
    )
    def _compute_rmg_withholding_applied(self):
        bks_moves = self.filtered(
            lambda move: move._bks_withholding_on_invoice_enabled() and move.rmg_has_withholding
        )
        super(AccountMove, self - bks_moves)._compute_rmg_withholding_applied()
        for move in bks_moves:
            if move.state != "posted":
                move.rmg_withholding_applied = 0.0
                move.rmg_withholding_net_settled = 0.0
                continue
            move.rmg_withholding_applied = move._rmg_measured_withholding()
            move.rmg_withholding_net_settled = abs(move.amount_total) - abs(move.amount_residual)
