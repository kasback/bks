# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, models
from odoo.exceptions import UserError


class PurchaseRequestAllocation(models.Model):
    _inherit = "purchase.request.allocation"

    def _bks_block_po_folder_edit(self):
        if not self.env.context.get("bks_pr_lines_readonly"):
            return
        raise UserError(
            _(
                "Les allocations ne sont pas modifiables depuis le "
                "raccourci dossier du bon de commande / demande de prix."
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
