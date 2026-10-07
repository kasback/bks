# Copyright 2025 Spearhead - Ricardo Jara
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class BksPaymentCancelWizard(models.TransientModel):
    _name = "bks.payment.cancel.wizard"
    _description = "Confirmation annulation paiement"

    payment_ids = fields.Many2many(
        comodel_name="account.payment",
        string="Paiements",
        required=True,
    )

    def action_confirm_cancel(self):
        self.ensure_one()
        return self.payment_ids.with_context(
            bks_skip_cancel_warning=True
        ).action_cancel()
