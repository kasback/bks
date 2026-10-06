# Copyright 2025 Spearhead - Ricardo Jara
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _post_payments(self, to_process, edit_mode=False):
        """Lance la validation tiers puis confirme (facture « en cours de paiement »)."""
        payments = self.env["account.payment"]
        for vals in to_process:
            payments |= vals["payment"]
        to_review = payments.filtered("need_validation").filtered(
            lambda pay: not pay.review_ids
        )
        if to_review:
            to_review.request_validation()
        return super()._post_payments(to_process, edit_mode=edit_mode)
