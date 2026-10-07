# Copyright <2020> PESOL <info@pesol.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

from odoo import api, models
from odoo.api import NewId
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "tier.validation"]
    _state_from = ["draft"]
    _state_to = ["posted"]

    _tier_validation_manual_config = False

    def _bks_tier_definitions_apply(self):
        self.ensure_one()
        tiers = self.env["tier.definition"].search(
            [
                ("model", "=", self._name),
                ("company_id", "in", [False] + self._get_company().ids),
            ]
        )
        return any(self.evaluate_tier(tier) for tier in tiers)

    @api.depends("need_validation", "state", "company_id")
    def _compute_hide_post_button(self):
        result = super()._compute_hide_post_button()
        for move in self:
            if move.state != "draft":
                continue
            if move.need_validation:
                move.hide_post_button = True
            elif isinstance(move.id, NewId) and move._bks_tier_definitions_apply():
                move.hide_post_button = True
        return result

    def _get_under_validation_exceptions(self):
        return super()._get_under_validation_exceptions() + ["needed_terms_dirty"]

    def _get_validation_exceptions(self, extra_domain=None, add_base_exceptions=True):
        res = super()._get_validation_exceptions(extra_domain, add_base_exceptions)
        am_exceptions = [
            "amount_total",
            "needed_terms_dirty",
            "is_manually_modified",
            "is_move_sent",
            "sending_data",
            "matched_payment_ids",
            "payment_state",
        ]
        return res + am_exceptions

    def _get_to_validate_message_name(self):
        name = super()._get_to_validate_message_name()
        if self.move_type == "in_invoice":
            name = self.env._("Bill")
        elif self.move_type == "in_refund":
            name = self.env._("Refund")
        elif self.move_type == "out_invoice":
            name = self.env._("Invoice")
        elif self.move_type == "out_refund":
            name = self.env._("Credit Note")
        return name

    def action_post(self):
        for move in self:
            if not move._bks_tier_definitions_apply():
                continue
            if isinstance(move.id, NewId):
                raise ValidationError(
                    self.env._(
                        "Enregistrez la facture avant de la comptabiliser."
                    )
                )
            if not move.review_ids:
                move.request_validation()
            if move.validation_status != "validated":
                raise ValidationError(
                    self.env._(
                        "Cette pièce doit être approuvée dans le circuit de "
                        "validation avant d'être comptabilisée."
                    )
                )
        return super().action_post()
