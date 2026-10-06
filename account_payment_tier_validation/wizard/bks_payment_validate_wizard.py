# Copyright 2025 Spearhead - Ricardo Jara
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class BksPaymentValidateWizard(models.TransientModel):
    _name = "bks.payment.validate.wizard"
    _description = "Confirmation validation paiement (iMal)"

    payment_ids = fields.Many2many(
        comodel_name="account.payment",
        string="Paiements",
        required=True,
    )

    def action_confirm_validate(self):
        self.ensure_one()
        return self.payment_ids.with_context(
            bks_skip_validate_warning=True
        ).action_validate()
