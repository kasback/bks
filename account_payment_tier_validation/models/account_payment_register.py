# Copyright 2025 Spearhead - Ricardo Jara
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    bks_can_edit_payment_amount = fields.Boolean(
        compute="_compute_bks_can_edit_payment_amount",
    )

    @api.depends_context("uid")
    def _compute_bks_can_edit_payment_amount(self):
        can = self.env.user.has_group(
            "account_payment_tier_validation.group_bks_payment_amount"
        )
        for wizard in self:
            wizard.bks_can_edit_payment_amount = can

    def _bks_check_register_amount_edit(self):
        if self.env.su or self.env.user.has_group(
            "account_payment_tier_validation.group_bks_payment_amount"
        ):
            return
        for wizard in self:
            if not wizard.currency_id or not wizard.journal_id:
                continue
            if wizard.custom_user_amount:
                raise UserError(
                    _("Vous n'avez pas le droit de modifier le montant du paiement.")
                )
            totals = wizard._get_total_amounts_to_pay(wizard.batches)
            allowed = (
                totals["amount_by_default"],
                totals["amount_for_difference"],
                totals["full_amount"],
                totals["full_amount_for_difference"],
            )
            if all(
                not wizard.currency_id.is_zero(wizard.amount - value)
                for value in allowed
            ):
                raise UserError(
                    _("Vous n'avez pas le droit de modifier le montant du paiement.")
                )

    def _bks_check_outbound_bank_account(self):
        for wizard in self:
            if wizard.can_group_payments and wizard.group_payment:
                continue
            if (
                not wizard.require_partner_bank_account
                and not wizard._bks_ma_transfer_requires_partner_bank()
            ):
                continue
            if not wizard.partner_bank_id:
                raise ValidationError(
                    _(
                        "Le compte bancaire du bénéficiaire est obligatoire "
                        "pour un virement bancaire."
                    )
                )

    def action_create_payments(self):
        self.line_ids.move_id._bks_raise_if_open_payment()
        self._bks_sync_payment_method_line_from_dgi()
        self._bks_check_register_amount_edit()
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
