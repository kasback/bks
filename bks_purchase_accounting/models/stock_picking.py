from odoo import _, fields, models
from odoo.exceptions import UserError


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
            fnp_pickings.sudo()._bks_generate_fnp_provisions()
        return res

    def _bks_generate_fnp_provisions(self):
        Fnp = self.env["bks.purchase.fnp"]
        for picking in self.sudo():
            if picking.bks_fnp_move_ids:
                continue
            Fnp._create_provision_from_picking(picking)

    def action_bks_generate_fnp(self):
        for picking in self:
            if picking.state != "done":
                raise UserError(_("La réception doit être validée."))
            if picking.picking_type_code != "incoming" or not picking.purchase_id:
                raise UserError(_("La FNP ne s'applique qu'aux réceptions fournisseur."))
            if picking.bks_fnp_move_ids:
                raise UserError(
                    _("Une provision FNP existe déjà pour la réception %s.") % picking.name
                )
        self._bks_generate_fnp_provisions()
