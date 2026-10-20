# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, models
from odoo.exceptions import UserError


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def action_open_request_line_tree_view(self):
        """Lignes DA en lecture seule depuis l'icône dossier (DP/BDC)."""
        action = super().action_open_request_line_tree_view()
        ctx = action.get("context") or {}
        if not isinstance(ctx, dict):
            ctx = {}
        else:
            ctx = dict(ctx)
        ctx["bks_pr_lines_readonly"] = True
        action["context"] = ctx
        form_view = self.env.ref(
            "bks_purchase_approval.purchase_request_line_form_po_folder_readonly",
            raise_if_not_found=False,
        )
        if form_view:
            action["views"] = [
                (False, "list"),
                (form_view.id, "form"),
            ]
            action["view_mode"] = "list,form"
        return action

    def _bks_block_po_folder_edit(self):
        if not self.env.context.get("bks_pr_lines_readonly"):
            return
        raise UserError(
            _(
                "Les lignes de bon de commande ne sont pas modifiables "
                "depuis le raccourci dossier (onglet lié à la demande d'achat)."
            )
        )

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("bks_pr_lines_readonly"):
            self._bks_block_po_folder_edit()
        return super().create(vals_list)

    def write(self, vals):
        if vals:
            self._bks_block_po_folder_edit()
        return super().write(vals)

    def unlink(self):
        self._bks_block_po_folder_edit()
        return super().unlink()
