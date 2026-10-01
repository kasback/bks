# Copyright 2025 Spearhead - Ricardo Jara
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class AccountPayment(models.Model):
    _name = "account.payment"
    _inherit = ["account.payment", "tier.validation"]
    _state_from = ["draft"]
    _state_to = ["in_process", "paid"]
    _cancel_state = "canceled"

    _tier_validation_manual_config = False

    def _get_to_validate_message_name(self):
        if self.payment_type == "outbound":
            return self.env._("Vendor Payment")
        if self.payment_type == "inbound":
            return self.env._("Customer Payment")
        return super()._get_to_validate_message_name()

    def _allow_to_remove_reviews(self, values):
        if values.get(self._state_field) == "rejected":
            return True
        return super()._allow_to_remove_reviews(values)
