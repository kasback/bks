from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    bks_fnp_ids = fields.One2many(
        "bks.purchase.fnp",
        "purchase_order_id",
        string="Provisions FNP",
        readonly=True,
    )
    bks_fnp_count = fields.Integer(compute="_compute_bks_fnp_count")

    def _compute_bks_fnp_count(self):
        for order in self:
            order.bks_fnp_count = len(order.bks_fnp_ids)

    def action_view_bks_fnp(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "bks_purchase_accounting.action_bks_purchase_fnp"
        )
        action["domain"] = [("purchase_order_id", "=", self.id)]
        action["context"] = dict(self.env.context, default_purchase_order_id=self.id)
        return action
