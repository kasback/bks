# Copyright 2025 Spearhead - Ricardo Jara
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import ValidationError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _bks_check_outbound_bank_account(self):
        for wizard in self:
            if wizard.payment_type != "outbound":
                continue
            if wizard.journal_id.type != "bank":
                continue
            if wizard.can_group_payments and wizard.group_payment:
                continue
            if not wizard.partner_bank_id:
                raise ValidationError(
                    _(
                        "Le compte bancaire du bénéficiaire est obligatoire "
                        "pour un virement bancaire."
                    )
                )

    def action_create_payments(self):
        self._bks_check_outbound_bank_account()
        return super().action_create_payments()

    def _init_payments(self, to_process, edit_mode=False):
        return super(
            AccountPaymentRegister,
            self.with_context(bks_from_payment_register=True),
        )._init_payments(to_process, edit_mode=edit_mode)

    def _bks_payment_vals_needing_tier_hold(self, to_process):
        payments = self.env["account.payment"]
        for vals in to_process:
            payments |= vals["payment"]
        return payments._bks_requires_tier_before_validate()

    def _bks_store_register_reconcile_info(self, to_process, held_payments):
        for vals in to_process:
            payment = vals["payment"]
            if payment not in held_payments:
                continue
            write_vals = {
                "bks_register_reconcile_line_ids": [
                    (6, 0, vals["to_reconcile"].ids)
                ],
            }
            if "rate" in vals:
                write_vals["bks_register_forced_rate"] = vals["rate"]
            payment.write(write_vals)

    def _bks_link_payments_to_invoices(self, process_vals):
        """Lien facture ↔ paiement (smart button) même si lettrage différé."""
        for vals in process_vals:
            vals["to_reconcile"].move_id.matched_payment_ids += vals["payment"]

    def _post_payments(self, to_process, edit_mode=False):
        """Brouillon + circuit tier ; comptabilisation au bouton Valider."""
        held = self._bks_payment_vals_needing_tier_hold(to_process)
        to_post = [
            vals for vals in to_process if vals["payment"] not in held
        ]
        if held:
            held.filtered(lambda pay: not pay.review_ids).request_validation()
            self._bks_store_register_reconcile_info(to_process, held)
            self._bks_link_payments_to_invoices(
                [vals for vals in to_process if vals["payment"] in held]
            )
            held._bks_prepare_draft_accounting()
        if to_post:
            self._bks_link_payments_to_invoices(to_post)
            super()._post_payments(to_post, edit_mode=edit_mode)

    def _reconcile_payments(self, to_process, edit_mode=False):
        held = self._bks_payment_vals_needing_tier_hold(to_process)
        to_reconcile = [
            vals for vals in to_process if vals["payment"] not in held
        ]
        if to_reconcile:
            super()._reconcile_payments(to_reconcile, edit_mode=edit_mode)
