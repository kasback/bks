# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import UserError

from .account_move import _BKS_ENTRY_REVERSE_GROUP


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    def reverse_moves(self, is_modify=False):
        moves = self.mapped("move_ids")
        moves._bks_raise_if_missing_entry_group(
            _BKS_ENTRY_REVERSE_GROUP,
            _(
                "L'extourne d'une pièce comptable est réservée au groupe "
                "« Extourner les pièces comptables »."
            ),
        )
        invoices = moves.filtered(lambda move: move.move_type != "entry")
        blocked = invoices.filtered(
            lambda move: not move.bks_user_can_finance_move_actions
        )
        if blocked:
            raise UserError(
                _(
                    "La création d'un avoir est réservée à la direction "
                    "financière (comptabilité / administration)."
                )
            )
        return super().reverse_moves(is_modify=is_modify)
