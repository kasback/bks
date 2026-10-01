from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    bks_fnp_move_ids = fields.One2many(
        "bks.purchase.fnp",
        "picking_id",
        string="Provisions FNP",
        readonly=True,
    )
    bks_fnp_count = fields.Integer(compute="_compute_bks_fnp_count")

    def _compute_bks_fnp_count(self):
        for picking in self:
            picking.bks_fnp_count = len(picking.bks_fnp_move_ids)

    def _action_done(self):
        res = super()._action_done()
        fnp_pickings = self.filtered(
            lambda p: p.picking_type_code == "incoming"
            and p.purchase_id
            and not p.bks_fnp_move_ids
        )
        if fnp_pickings:
            fnp_pickings._bks_generate_fnp_provisions()
        return res

    def _bks_generate_fnp_provisions(self):
        Fnp = self.env["bks.purchase.fnp"]
        for picking in self:
            if picking.bks_fnp_move_ids:
                continue
            Fnp._create_provision_from_picking(picking)
