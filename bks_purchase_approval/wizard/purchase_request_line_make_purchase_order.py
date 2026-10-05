# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Demande de prix (DP / RFQ) — pas bon de commande confirmé (BC).
_BKS_RFQ_STATES = ("draft", "sent")


class PurchaseRequestLineMakePurchaseOrder(models.TransientModel):
    _inherit = "purchase.request.line.make.purchase.order"

    purchase_order_id = fields.Many2one(
        domain=[
            ("state", "in", _BKS_RFQ_STATES),
        ],
    )

    def make_purchase_order(self):
        for wizard in self:
            po = wizard.purchase_order_id
            if po and po.state not in _BKS_RFQ_STATES:
                raise UserError(
                    _(
                        "Le document « %(name)s » n'est pas une demande de "
                        "prix en brouillon : seules les DP peuvent être "
                        "complétées depuis la DA.",
                        name=po.display_name,
                    )
                )
        return super().make_purchase_order()
