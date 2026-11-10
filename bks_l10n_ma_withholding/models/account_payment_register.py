from odoo import Command, api, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _bks_payment_withholding_on_invoice(self):
        self.ensure_one()
        return bool(self.company_id.bks_l10n_ma_withholding_on_invoice)

    @api.depends(
        "company_id",
        "can_edit_wizard",
        "can_group_payments",
        "group_payment",
        "payment_type",
    )
    def _compute_display_withholding(self):
        super()._compute_display_withholding()
        for wizard in self:
            if wizard._bks_payment_withholding_on_invoice() and wizard.payment_type == "outbound":
                wizard.display_withholding = False

    @api.depends("line_ids", "payment_date", "company_id", "payment_type", "display_withholding")
    def _compute_withholding_line_ids(self):
        super()._compute_withholding_line_ids()
        for wizard in self:
            if wizard._bks_payment_withholding_on_invoice() and wizard.payment_type == "outbound":
                wizard.withholding_line_ids = [Command.clear()]

    @api.depends("withholding_line_ids", "company_id", "payment_type")
    def _compute_should_withhold_tax(self):
        super()._compute_should_withhold_tax()
        for wizard in self:
            if wizard._bks_payment_withholding_on_invoice() and wizard.payment_type == "outbound":
                wizard.should_withhold_tax = False

    def _rmg_batch_withholding_commands(self, batch_result):
        if self._bks_payment_withholding_on_invoice():
            return []
        return super()._rmg_batch_withholding_commands(batch_result)

    def _create_payment_vals_from_batch(self, batch_result):
        payment_vals = super()._create_payment_vals_from_batch(batch_result)
        if (
            self._bks_payment_withholding_on_invoice()
            and batch_result["payment_values"].get("payment_type") == "outbound"
        ):
            payment_vals["should_withhold_tax"] = False
            payment_vals.pop("withholding_line_ids", None)
        return payment_vals
