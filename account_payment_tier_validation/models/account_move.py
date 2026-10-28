# Copyright 2025 Spearhead - Ricardo Jara
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    bks_draft_payment_name = fields.Char(
        string="Numéro de paiement",
        compute="_compute_bks_draft_payment_name",
    )

    bks_draft_payment_name = fields.Char(
        string="Numéro de paiement",
        compute="_compute_bks_draft_payment_name",
    )

    @api.depends("state", "name", "origin_payment_id.name")
    def _compute_bks_draft_payment_name(self):
        """Numéro de paiement tant que la pièce n'a pas son numéro de journal."""
        for move in self:
            payment_name = move.sudo().origin_payment_id.name
            if (
                move.state != "posted"
                and payment_name
                and payment_name != "/"
                and (not move.name or move.name == "/")
            ):
                move.bks_draft_payment_name = payment_name
            else:
                move.bks_draft_payment_name = False

    def _bks_blocking_matched_payments(self):
        self.ensure_one()
        return self.matched_payment_ids.filtered(
            lambda pay: pay.state in ("draft", "in_process", "paid")
        )

    def _bks_raise_if_payments_block(self, action_label):
        for move in self:
            if not move.is_invoice(include_receipts=True):
                continue
            payments = move._bks_blocking_matched_payments()
            if payments:
                names = ", ".join(payments[:10].mapped("display_name"))
                raise UserError(
                    _(
                        "Impossible de %(action)s cette facture : un paiement "
                        "est lié (brouillon, en cours ou validé) (%(payments)s).",
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

    def _bks_settlement_payments(self):
        """Paiements de la facture, hors annulés et hors retenue de garantie."""
        self.ensure_one()
        payments = (self.matched_payment_ids | self.reconciled_payment_ids).exists()
        payments = payments.filtered(lambda pay: pay.state != "canceled")
        if "bks_guarantee_move_id" in payments._fields:
            payments = payments.filtered(lambda pay: not pay.bks_guarantee_move_id)
        return payments

    def _bks_raise_if_open_payment(self):
        """Une facture n'accepte qu'un paiement tant qu'il n'est pas annulé."""
        details = []
        for move in self.filtered(lambda move: move.is_invoice(include_receipts=True)):
            payments = move._bks_settlement_payments()
            if not payments:
                continue
            names = ", ".join(payments[:5].mapped("display_name"))
            details.append(
                _("%(invoice)s : %(payments)s", invoice=move.display_name, payments=names)
            )
        if details:
            raise UserError(
                _(
                    "Un paiement non annulé existe déjà pour : %(details)s. "
                    "Une facture ne peut avoir qu'un seul paiement. "
                    "Annulez le paiement existant pour en créer un autre.",
                    details=" ; ".join(details),
                )
            )

    def write(self, vals):
        res = super().write(vals)
        if "matched_payment_ids" in vals:
            duplicates = self.filtered(
                lambda move: move.is_invoice(include_receipts=True)
                and len(move._bks_settlement_payments()) > 1
            )
            duplicates._bks_raise_if_open_payment()
        return res


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def action_register_payment(self, ctx=None):
        self.move_id._bks_raise_if_open_payment()
        return super().action_register_payment(ctx=ctx)
