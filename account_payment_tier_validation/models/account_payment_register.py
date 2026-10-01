# Copyright 2025 Spearhead - Ricardo Jara
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _post_payments(self, to_process, edit_mode=False):
        """Keep payments that need a tier review in draft instead of posting."""
        payments = self.env["account.payment"]
        for vals in to_process:
            payments |= vals["payment"]
        to_review = payments.filtered("need_validation")
        to_post = payments - to_review
        if to_review:
            to_review.request_validation()
        if to_post:
            to_post.with_context(skip_sale_auto_invoice_send=True).action_post()
