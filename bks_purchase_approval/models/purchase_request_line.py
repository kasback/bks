# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseRequestLine(models.Model):
    _inherit = "purchase.request.line"

    bks_readonly_po_folder = fields.Boolean(
        string="Lecture seule (dossier BDC)",
        compute="_compute_bks_readonly_po_folder",
    )

    @api.depends_context("bks_pr_lines_readonly")
    def _compute_bks_readonly_po_folder(self):
        readonly = bool(self.env.context.get("bks_pr_lines_readonly"))
        for line in self:
            line.bks_readonly_po_folder = readonly

    def _bks_block_po_folder_line_edit(self):
        if not self.env.context.get("bks_pr_lines_readonly"):
            return
        raise UserError(
            _(
                "Les lignes de demande d'achat ne sont pas modifiables "
                "depuis cette vue (smart button Lignes ou raccourci dossier "
                "bon de commande / demande de prix)."
            )
        )

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("bks_pr_lines_readonly"):
            self._bks_block_po_folder_line_edit()
        return super().create(vals_list)

    def write(self, vals):
        if vals:
            self._bks_block_po_folder_line_edit()
        return super().write(vals)

    def unlink(self):
        self._bks_block_po_folder_line_edit()
        return super().unlink()
