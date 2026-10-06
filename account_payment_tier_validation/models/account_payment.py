# Copyright 2025 Spearhead - Ricardo Jara
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _name = "account.payment"
    _inherit = ["account.payment", "tier.validation"]
    _state_from = ["draft", "in_process"]
    # Circuit actif jusqu'à « Payé » ; « En cours » (wizard) reste possible sans blocage.
    _state_to = ["paid"]
    _cancel_state = "canceled"

    _tier_validation_manual_config = False

    def _check_tier_state_transition(self, vals):
        """Autoriser la confirmation (en cours) pendant le circuit de validation."""
        if vals.get(self._state_field) == "in_process":
            return False
        return super()._check_tier_state_transition(vals)

    def _bks_tier_definition_applies(self):
        self.ensure_one()
        tiers = (
            self.env["tier.definition"]
            .with_context(active_test=True)
            .search(
                [
                    ("model", "=", self._name),
                    ("company_id", "in", [False] + self._get_company().ids),
                ]
            )
        )
        return any(self.evaluate_tier(tier) for tier in tiers)

    def _tier_validation_check_state_on_write(self, vals):
        """Pas d'auto-validation : le circuit doit approuver explicitement."""
        new_state = vals.get(self._state_field)
        if new_state != "paid":
            return super()._tier_validation_check_state_on_write(vals)
        for rec in self:
            if rec._tier_validation_get_current_state_value() not in (
                "draft",
                "in_process",
                False,
            ):
                continue
            if not rec._bks_tier_definition_applies():
                continue
            if not rec.review_ids:
                rec.request_validation()
            if rec.validation_status != "validated":
                pending = rec.review_ids.filtered(
                    lambda review: review.status == "pending"
                ).mapped("name")
                steps = "\n- ".join(pending) if pending else _("(aucune)")
                raise ValidationError(
                    _(
                        "Ce paiement doit être approuvé dans le circuit de "
                        "validation avant d'être marqué comme payé.\n"
                        "Étapes en attente :\n- %(steps)s",
                        steps=steps,
                    )
                )
            if rec.review_ids and rec.validation_status != "validated":
                raise ValidationError(
                    _(
                        "Un circuit de validation est encore ouvert sur ce "
                        "paiement."
                    )
                )

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
