# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_VENDOR_BILL_MOVE_TYPES = frozenset({"in_invoice", "in_refund", "in_receipt"})

_BKS_FINANCE_MOVE_CREDIT_DRAFT_GROUP = (
    "bks_purchase_approval.group_bks_finance_move_credit_draft"
)


class AccountMove(models.Model):
    _inherit = "account.move"

    bks_operation_department_manual_id = fields.Many2one(
        comodel_name="hr.department",
        string="Unité opérationnelle (saisie)",
        copy=False,
        help="Saisie manuelle pour les factures fournisseur sans bon de commande.",
    )
    bks_operation_department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Unité opérationnelle (DA)",
        compute="_compute_bks_operation_department_id",
        inverse="_inverse_bks_operation_department_id",
        store=True,
        readonly=False,
        help="Issu du BDC, d'une saisie manuelle ou du département du créateur.",
    )
    bks_vendor_locked_from_po = fields.Boolean(
        compute="_compute_bks_vendor_locked_from_po",
        help="Fournisseur figé lorsque la facture est liée à un bon de commande.",
    )
    bks_user_can_finance_move_actions = fields.Boolean(
        compute="_compute_bks_user_can_finance_move_actions",
        help="Avoir et remise en brouillon réservés à la direction financière.",
    )
    bks_invoice_reception_date = fields.Date(
        string="Date réception effective de la facture",
        copy=False,
        tracking=True,
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

    def action_post(self):
        missing = self.filtered(
            lambda move: move.move_type == "in_invoice"
            and not move.bks_invoice_reception_date
        )
        if missing:
            raise UserError(
                _(
                    "La date de réception effective de la facture est obligatoire."
                )
            )
        return super().action_post()

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

    @api.model
    def _bks_department_for_user(self, user, company):
        if not user:
            return self.env["hr.department"]
        employee = user.with_company(company).employee_id
        if not employee:
            employee = self.env["hr.employee"].sudo().search(
                [
                    ("user_id", "=", user.id),
                    "|",
                    ("company_id", "=", False),
                    ("company_id", "=", company.id),
                ],
                limit=1,
            )
        return employee.department_id if employee else self.env["hr.department"]

    @api.depends(
        "invoice_line_ids.purchase_line_id.order_id.bks_operation_department_id",
        "line_ids.purchase_line_id.order_id.bks_operation_department_id",
        "bks_operation_department_manual_id",
        "create_uid",
        "company_id",
        "purchase_order_count",
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
            if not department and move.bks_operation_department_manual_id:
                department = move.bks_operation_department_manual_id
            if (
                not department
                and move.move_type in _VENDOR_BILL_MOVE_TYPES
                and not move.purchase_order_count
            ):
                company = move.company_id or move.env.company
                department = move._bks_department_for_user(move.create_uid, company)
            move.bks_operation_department_id = department
        self._bks_refresh_coordonnateur_reviewers()

    def _inverse_bks_operation_department_id(self):
        for move in self:
            if move.purchase_order_count:
                continue
            move.bks_operation_department_manual_id = move.bks_operation_department_id

    def request_validation(self):
        missing = self.filtered(
            lambda move: move.move_type in _VENDOR_BILL_MOVE_TYPES
            and not move.bks_operation_department_id
        )
        if missing:
            raise UserError(
                _(
                    "Indiquez l'unité opérationnelle sur la facture fournisseur "
                    "avant de lancer la validation (obligatoire pour le "
                    "co-ordonnateur lorsqu'il n'y a pas de DA ni de bon de "
                    "commande)."
                )
            )
        return super().request_validation()

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
