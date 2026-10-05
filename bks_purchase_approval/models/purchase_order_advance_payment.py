# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class PurchaseOrderAdvancePayment(models.TransientModel):
    _inherit = "purchase.order.advance.payment"

    def action_create_advance_bill(self):
        self.env["purchase.order"]._bks_check_can_create_vendor_bill()
        return super().action_create_advance_bill()
