from odoo import models


class PurchaseOrderAdvancePayment(models.TransientModel):
    _inherit = "purchase.order.advance.payment"

    def _prepare_invoice_values(self, order, name, amount, so_line):
        vals = super()._prepare_invoice_values(order, name, amount, so_line)
        account = order.partner_id.with_company(
            order.company_id
        ).property_account_advance_id
        if account:
            for command in vals.get("invoice_line_ids", []):
                if isinstance(command, (list, tuple)) and len(command) == 3:
                    command[2]["account_id"] = account.id
        return vals
