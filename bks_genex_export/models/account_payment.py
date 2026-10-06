from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    genex_exported = fields.Boolean(
        related="move_id.genex_exported",
        string="Exporté GENEX",
        store=True,
        readonly=True,
    )
    bks_show_genex_export_button = fields.Boolean(
        compute="_compute_bks_genex_payment_buttons",
    )

    @api.depends(
        "state",
        "validation_status",
        "move_id",
        "move_id.genex_exported",
        "bks_tier_governed",
    )
    def _compute_bks_genex_payment_buttons(self):
        for pay in self:
            pay.bks_show_genex_export_button = (
                pay.bks_tier_governed
                and pay.validation_status == "validated"
                and pay.state == "in_process"
                and pay.move_id
                and not pay.move_id.genex_exported
            )

    @api.depends(
        "state",
        "move_id",
        "move_id.genex_exported",
        "validation_status",
        "amount",
        "payment_type",
        "partner_type",
        "company_id",
        "bks_tier_governed",
    )
    def _compute_bks_payment_buttons(self):
        super()._compute_bks_payment_buttons()
        for pay in self.filtered("bks_tier_governed"):
            genex_exported = bool(pay.move_id and pay.move_id.genex_exported)
            pay.bks_show_validate_button = (
                pay.validation_status == "validated"
                and pay.state == "in_process"
                and genex_exported
            )
            pay.bks_show_reset_to_draft_button = (
                pay.state not in ("draft", "canceled") and not genex_exported
            )

    def _bks_check_genex_export_eligibility(self):
        errors = []
        for pay in self:
            if not pay.bks_tier_governed:
                errors.append(
                    _("%(name)s : hors circuit de règlement.", name=pay.display_name)
                )
                continue
            if pay.validation_status != "validated":
                errors.append(
                    _(
                        "%(name)s : le circuit de validation n'est pas approuvé.",
                        name=pay.display_name,
                    )
                )
            if pay.state != "in_process":
                errors.append(
                    _(
                        "%(name)s : le paiement doit être en cours de traitement.",
                        name=pay.display_name,
                    )
                )
            if not pay.move_id:
                errors.append(
                    _(
                        "%(name)s : aucune écriture comptable associée.",
                        name=pay.display_name,
                    )
                )
            elif pay.move_id.genex_exported:
                errors.append(
                    _(
                        "%(name)s : déjà exporté GENEX.",
                        name=pay.display_name,
                    )
                )
        if errors:
            raise UserError("\n".join(errors))

    def action_open_genex_export_wizard(self):
        self._bks_check_genex_export_eligibility()
        moves = self.mapped("move_id")
        wizard = self.env["bks.genex.export.wizard"].create(
            {
                "date_from": min(moves.mapped("date")),
                "date_to": max(moves.mapped("date")),
                "move_ids": [(6, 0, moves.ids)],
                "bks_payment_export": True,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Export GENEX"),
            "res_model": "bks.genex.export.wizard",
            "view_mode": "form",
            "res_id": wizard.id,
            "target": "new",
        }

    def action_validate(self):
        governed = self._bks_requires_tier_before_validate()
        not_exported = governed.filtered(
            lambda pay: not (pay.move_id and pay.move_id.genex_exported)
        )
        if not_exported:
            raise ValidationError(
                _(
                    "Exportez d'abord le paiement vers GENEX avant de le "
                    "comptabiliser définitivement."
                )
            )
        return super().action_validate()

    def action_draft(self):
        exported = self.filtered(lambda pay: pay.move_id and pay.move_id.genex_exported)
        if exported:
            raise UserError(
                _(
                    "Impossible de remettre en brouillon un paiement "
                    "déjà exporté GENEX."
                )
            )
        return super().action_draft()
