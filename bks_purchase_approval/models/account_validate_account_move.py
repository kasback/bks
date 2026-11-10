# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models

from .account_move import _BKS_ENTRY_POST_GROUP


class ValidateAccountMove(models.TransientModel):
    _inherit = "validate.account.move"

    def validate_move(self):
        self.mapped("move_ids")._bks_raise_if_missing_entry_group(
            _BKS_ENTRY_POST_GROUP,
            _(
                "La comptabilisation d'une pièce comptable est réservée au "
                "groupe « Comptabiliser les pièces comptables »."
            ),
        )
        return super().validate_move()
