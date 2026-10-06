# Copyright 2025 Spearhead - Ricardo Jara
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _bks_blocking_matched_payments(self):
        self.ensure_one()
        return self.matched_payment_ids.filtered(
            lambda pay: pay.state in ("in_process", "paid")
        )

    def _bks_raise_if_payments_block(self, action_label):
        for move in self:
            if not move.is_invoice(include_receipts=True):
                continue
            payments = move._bks_blocking_matched_payments()
            if payments:
                names = ", ".join(payments.mapped("name")[:10])
                raise UserError(
                    _(
                        "Impossible de %(action)s cette facture : un paiement "
                        "est en cours ou validé (%(payments)s).",
                        action=action_label,
                        payments=names,
                    )
                )

    def button_draft(self):
        self._bks_raise_if_payments_block(_("remettre en brouillon"))
        return super().button_draft()

    def button_cancel(self):
        self._bks_raise_if_payments_block(_("annuler"))
        return super().button_cancel()

    def action_reverse(self):
        self._bks_raise_if_payments_block(_("extourner"))
        return super().action_reverse()
