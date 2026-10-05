# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_VENDOR_BILL_MOVE_TYPES = frozenset({"in_invoice", "in_refund", "in_receipt"})

_BKS_FINANCE_MOVE_CREDIT_DRAFT_GROUP = (
    "bks_purchase_approval.group_bks_finance_move_credit_draft"
)


class AccountMove(models.Model):
    _inherit = "account.move"

    bks_operation_department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Unité opérationnelle (DA)",
        compute="_compute_bks_operation_department_id",
        store=True,
        help="Département issu des bons de commande liés à cette facture.",
    )
    bks_vendor_locked_from_po = fields.Boolean(
        compute="_compute_bks_vendor_locked_from_po",
        help="Fournisseur figé lorsque la facture est liée à un bon de commande.",
    )
    bks_user_can_finance_move_actions = fields.Boolean(
        compute="_compute_bks_user_can_finance_move_actions",
        help="Avoir et remise en brouillon réservés à la direction financière.",
    )

    @api.model
    def _bks_user_can_finance_move_credit_draft(self):
        user = self.env.user
        if user.has_group("base.group_system"):
            return True
        if user.has_group(_BKS_FINANCE_MOVE_CREDIT_DRAFT_GROUP):
            return True
        return False

    @api.depends_context("uid")
    def _compute_bks_user_can_finance_move_actions(self):
        can = self._bks_user_can_finance_move_credit_draft()
        for move in self:
            move.bks_user_can_finance_move_actions = can

    def button_draft(self):
        blocked = self.filtered(
            lambda move: not move.bks_user_can_finance_move_actions
        )
        if blocked:
            raise UserError(
                _(
                    "La remise en brouillon est réservée à la direction "
                    "financière (comptabilité / administration)."
                )
            )
        return super().button_draft()

    def action_reverse(self):
        blocked = self.filtered(
            lambda move: not move.bks_user_can_finance_move_actions
        )
        if blocked:
            raise UserError(
                _(
                    "La création d'un avoir est réservée à la direction "
                    "financière (comptabilité / administration)."
                )
            )
        return super().action_reverse()

    @api.depends("purchase_order_count", "move_type")
    def _compute_bks_vendor_locked_from_po(self):
        for move in self:
            move.bks_vendor_locked_from_po = (
                move.move_type in _VENDOR_BILL_MOVE_TYPES
                and move.purchase_order_count > 0
            )

    @api.depends(
        "invoice_line_ids.purchase_line_id.order_id.bks_operation_department_id",
        "line_ids.purchase_line_id.order_id.bks_operation_department_id",
    )
    def _compute_bks_operation_department_id(self):
        for move in self:
            department = self.env["hr.department"]
            orders = (
                move.invoice_line_ids.purchase_line_id.order_id
                | move.line_ids.purchase_line_id.order_id
            )
            for order in orders:
                if order.bks_operation_department_id:
                    department = order.bks_operation_department_id
                    break
            move.bks_operation_department_id = department

    def _get_under_validation_exceptions(self):
        return super()._get_under_validation_exceptions() + [
            "bks_operation_department_id",
        ]

    def _get_after_validation_exceptions(self):
        return super()._get_after_validation_exceptions() + [
            "bks_operation_department_id",
        ]

    def write(self, vals):
        if "partner_id" in vals:
            locked = self.filtered(
                lambda move: move.bks_vendor_locked_from_po and move.state == "draft"
            )
            if locked:
                raise UserError(
                    _(
                        "Le fournisseur ne peut pas être modifié sur une "
                        "facture liée à un bon de commande."
                    )
                )
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            move_type = vals.get("move_type") or self.env.context.get(
                "default_move_type"
            )
            if move_type in _VENDOR_BILL_MOVE_TYPES:
                self.env["purchase.order"]._bks_check_can_create_vendor_bill()
                break
        return super().create(vals_list)
