from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_computed_taxes(self):
        taxes = super()._get_computed_taxes()
        if self.display_type != "product" or not self.move_id.is_invoice():
            return taxes
        regular = taxes.filtered(lambda tax: not tax.is_withholding_tax_on_payment)
        return regular | self._rmg_applicable_withholding_taxes(regular)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._bks_sync_withholding_taxes()
        return lines

    @api.onchange("product_id", "quantity", "price_unit", "discount")
    def _onchange_bks_sync_withholding_taxes(self):
        self._bks_sync_withholding_taxes()

    def _bks_sync_withholding_taxes(self):
        for line in self:
            if (
                line.display_type != "product"
                or not line.move_id.is_invoice()
                or line.move_id.state != "draft"
            ):
                continue
            base_taxes = line.tax_ids.filtered(
                lambda tax: not tax.is_withholding_tax_on_payment
            )
            if line.product_id and not base_taxes:
                base_taxes = line.product_id.taxes_id
                if line.move_id.is_purchase_document(include_receipts=True):
                    base_taxes = line.product_id.supplier_taxes_id
                base_taxes = base_taxes.filtered(
                    lambda tax: not tax.is_withholding_tax_on_payment
                )
            proposal = line._rmg_applicable_withholding_taxes(base_taxes)
            target = base_taxes | proposal
            if line.tax_ids != target:
                line.tax_ids = target
            if line.rmg_withholding_proposal_ids != proposal:
                line.rmg_withholding_proposal_ids = proposal

    def _rmg_withholding_taxes(self):
        self.ensure_one()
        if self.rmg_withholding_proposal_ids:
            return self.rmg_withholding_proposal_ids
        return super()._rmg_withholding_taxes()
