# Copyright 2025 Spearhead - Ricardo Jara
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AccountPayment(models.Model):
    _name = "account.payment"
    _inherit = ["account.payment", "tier.validation"]
    _state_from = ["draft", "in_process"]
    _state_to = ["paid"]
    _cancel_state = "canceled"

    _tier_validation_manual_config = False

    bks_tier_governed = fields.Boolean(compute="_compute_bks_payment_buttons")
    bks_show_confirm_button = fields.Boolean(compute="_compute_bks_payment_buttons")
    bks_show_validate_button = fields.Boolean(compute="_compute_bks_payment_buttons")
    bks_show_reset_to_draft_button = fields.Boolean(
        compute="_compute_bks_payment_buttons"
    )
    bks_show_cancel_button = fields.Boolean(compute="_compute_bks_payment_buttons")

    @api.model
    def _get_under_validation_exceptions(self):
        return super()._get_under_validation_exceptions() + [
            "bks_register_reconcile_line_ids",
            "bks_register_forced_rate",
        ]

    @api.model
    def _get_after_validation_exceptions(self):
        return super()._get_after_validation_exceptions() + [
            "bks_register_reconcile_line_ids",
            "bks_register_forced_rate",
        ]

    bks_register_reconcile_line_ids = fields.Many2many(
        comodel_name="account.move.line",
        relation="account_payment_bks_register_reconcile_line_rel",
        column1="payment_id",
        column2="line_id",
        string="Lignes à lettrer (wizard)",
        copy=False,
        help="Lignes facture en attente de lettrage après approbation du paiement.",
    )
    bks_register_forced_rate = fields.Float(
        string="Taux wizard",
        copy=False,
        help="Taux forcé lors de l'enregistrement du paiement (écart de change).",
    )

    @api.depends(
        "state",
        "move_id",
        "validation_status",
        "amount",
        "payment_type",
        "partner_type",
        "company_id",
    )
    def _compute_bks_payment_buttons(self):
        for pay in self:
            governed = pay._bks_tier_definition_applies()
            pay.bks_tier_governed = governed
            if governed:
                pay.bks_show_confirm_button = (
                    pay.state == "draft"
                    and pay.validation_status == "validated"
                )
                pay.bks_show_validate_button = (
                    pay.validation_status == "validated"
                    and pay.state == "in_process"
                )
                pay.bks_show_reset_to_draft_button = pay.state not in (
                    "draft",
                    "canceled",
                )
                pay.bks_show_cancel_button = pay.state in ("draft", "in_process")
            else:
                pay.bks_show_confirm_button = pay.state == "draft"
                pay.bks_show_validate_button = (
                    pay.state == "in_process" and not pay.move_id
                )
                pay.bks_show_reset_to_draft_button = pay.state not in ("draft",)
                pay.bks_show_cancel_button = pay.state == "draft" or (
                    pay.state == "in_process" and pay.is_sent
                )

    def _check_tier_state_transition(self, vals):
        if vals.get(self._state_field) != "paid":
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

    def _bks_keep_payment_move_in_draft(self):
        """Écriture de paiement en brouillon jusqu'à la validation finale."""
        self.ensure_one()
        return (
            self._bks_tier_definition_applies()
            and self.state not in ("paid", "canceled", "rejected")
        )

    def _bks_requires_tier_before_validate(self):
        return self.filtered(lambda pay: pay._bks_tier_definition_applies())

    def _tier_validation_check_state_on_write(self, vals):
        """Approbation tier obligatoire avant Valider (payé / comptabilisation)."""
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
                        "validation avant d'être validé.\n"
                        "Étapes en attente :\n- %(steps)s",
                        steps=steps,
                    )
                )

    def _bks_generate_draft_journal_entry(
        self, write_off_line_vals=None, force_balance=None, line_ids=None
    ):
        need_move = self.filtered(lambda p: not p.move_id and p.outstanding_account_id)
        assert len(self) == 1 or (
            not write_off_line_vals and not force_balance and not line_ids
        )
        move_vals = [
            pay._generate_move_vals(write_off_line_vals, force_balance, line_ids)
            for pay in need_move
        ]
        moves = self.env["account.move"].create(move_vals)
        for pay, move in zip(need_move, moves, strict=False):
            pay.with_context(skip_validation_check=True).write({"move_id": move.id})

    def _generate_journal_entry(self, write_off_line_vals=None, force_balance=None, line_ids=None):
        draft_only_ctx = self.env.context.get("bks_payment_draft_only")
        draft_payments = self.filtered(
            lambda p: draft_only_ctx or p._bks_keep_payment_move_in_draft()
        )
        to_confirm = self - draft_payments
        if to_confirm:
            super(AccountPayment, to_confirm)._generate_journal_entry(
                write_off_line_vals=write_off_line_vals,
                force_balance=force_balance,
                line_ids=line_ids,
            )
        if draft_payments:
            draft_payments._bks_generate_draft_journal_entry(
                write_off_line_vals=write_off_line_vals,
                force_balance=force_balance,
                line_ids=line_ids,
            )

    def _bks_ensure_outstanding_account(self):
        for pay in self:
            if pay.outstanding_account_id:
                continue
            pay.outstanding_account_id = pay._get_outstanding_account(
                pay.payment_type
            ).id

    def _bks_prepare_draft_accounting(self):
        for pay in self:
            pay._bks_ensure_outstanding_account()
            if not pay.move_id:
                pay.with_context(bks_payment_draft_only=True)._generate_journal_entry()
            elif pay.move_id.state != "draft":
                if getattr(pay, "genex_exported", False):
                    continue
                pay.move_id.button_draft()

    def _bks_reconcile_register_lines(self):
        domain = [
            ("parent_state", "=", "posted"),
            ("account_type", "in", self._get_valid_payment_account_types()),
            ("reconciled", "=", False),
        ]
        for payment in self:
            lines = payment.bks_register_reconcile_line_ids
            if not lines:
                continue
            payment_lines = payment.move_id.line_ids.filtered_domain(domain)
            extra_context = {}
            if payment.bks_register_forced_rate:
                extra_context["forced_rate_from_register_payment"] = (
                    payment.bks_register_forced_rate
                )
            for account in payment_lines.account_id:
                (payment_lines + lines).with_context(**extra_context).filtered_domain(
                    [
                        ("account_id", "=", account.id),
                        ("reconciled", "=", False),
                    ]
                ).reconcile()
            lines.move_id.matched_payment_ids += payment
            payment.with_context(skip_validation_check=True).write(
                {
                    "bks_register_reconcile_line_ids": [(5, 0, 0)],
                    "bks_register_forced_rate": 0.0,
                }
            )

    def action_post(self):
        """Confirmer : en cours sans comptabiliser (écriture reste en brouillon)."""
        governed = self.filtered(lambda pay: pay._bks_tier_definition_applies())
        not_approved = governed.filtered(
            lambda pay: pay.validation_status != "validated"
        )
        if not_approved:
            raise ValidationError(
                _(
                    "Confirmez le paiement uniquement après approbation "
                    "du circuit de règlement."
                )
            )
        standard = self - governed
        if standard:
            super(AccountPayment, standard).action_post()
        to_confirm = governed.filtered(lambda pay: pay.state in ("draft", False))
        if to_confirm:
            to_confirm._bks_prepare_draft_accounting()
            to_confirm._write({"state": "in_process"})
            to_confirm.invalidate_recordset(["state"])
        return True

    def _action_open_validate_wizard(self):
        self.ensure_one()
        wizard = self.env["bks.payment.validate.wizard"].create(
            {"payment_ids": [(6, 0, self.ids)]}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Valider le paiement"),
            "res_model": "bks.payment.validate.wizard",
            "view_mode": "form",
            "res_id": wizard.id,
            "target": "new",
        }

    def action_validate(self):
        governed = self._bks_requires_tier_before_validate()
        if governed and not self.env.context.get("bks_skip_validate_warning"):
            if len(governed) == 1:
                return governed._action_open_validate_wizard()
        blocked = governed.filtered(lambda pay: pay.validation_status != "validated")
        if blocked:
            raise ValidationError(
                _(
                    "Validez le paiement uniquement après approbation du "
                    "circuit de règlement."
                )
            )
        for pay in self:
            pay._bks_ensure_outstanding_account()
            if not pay.move_id:
                pay._generate_journal_entry()
            if pay.move_id.state == "draft":
                pay.move_id.action_post()
        self._bks_reconcile_register_lines()
        return super().action_validate()

    def action_draft(self):
        canceled = self.filtered(lambda pay: pay.state == "canceled")
        if canceled:
            raise UserError(
                _(
                    "Un paiement annulé ne peut pas être réinitialisé. "
                    "Créez un nouveau paiement."
                )
            )
        return super().action_draft()

    def _action_open_cancel_wizard(self):
        self.ensure_one()
        wizard = self.env["bks.payment.cancel.wizard"].create(
            {"payment_ids": [(6, 0, self.ids)]}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Annuler le paiement"),
            "res_model": "bks.payment.cancel.wizard",
            "view_mode": "form",
            "res_id": wizard.id,
            "target": "new",
        }

    def action_cancel(self):
        governed = self.filtered(lambda pay: pay._bks_tier_definition_applies())
        if governed and not self.env.context.get("bks_skip_cancel_warning"):
            if len(governed) == 1:
                return governed._action_open_cancel_wizard()
        return super().action_cancel()

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
