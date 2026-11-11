# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_VENDOR_BILL_MOVE_TYPES = frozenset({"in_invoice", "in_refund", "in_receipt"})

_BKS_FINANCE_MOVE_CREDIT_DRAFT_GROUP = (
    "bks_purchase_approval.group_bks_finance_move_credit_draft"
)
_BKS_ENTRY_POST_GROUP = "bks_purchase_approval.group_bks_entry_post"
_BKS_ENTRY_REVERSE_GROUP = "bks_purchase_approval.group_bks_entry_reverse"
_BKS_ENTRY_DRAFT_GROUP = "bks_purchase_approval.group_bks_entry_draft"


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
        precompute=True,
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
    bks_user_can_post_entry = fields.Boolean(
        compute="_compute_bks_user_can_entry_actions",
        help="Bouton Comptabiliser sur les pièces comptables hors facture.",
    )
    bks_user_can_reverse_entry = fields.Boolean(
        compute="_compute_bks_user_can_entry_actions",
        help="Bouton Extourner sur les pièces comptables hors facture.",
    )
    bks_user_can_draft_entry = fields.Boolean(
        compute="_compute_bks_user_can_entry_actions",
        help="Bouton Remettre en brouillon sur les pièces comptables hors facture.",
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

    @api.model
    def _bks_user_has_entry_button_group(self, xmlid):
        return self.env.user.has_group(xmlid)

    @api.depends_context("uid")
    def _compute_bks_user_can_entry_actions(self):
        can_post = self._bks_user_has_entry_button_group(_BKS_ENTRY_POST_GROUP)
        can_reverse = self._bks_user_has_entry_button_group(_BKS_ENTRY_REVERSE_GROUP)
        can_draft = self._bks_user_has_entry_button_group(_BKS_ENTRY_DRAFT_GROUP)
        for move in self:
            move.bks_user_can_post_entry = can_post
            move.bks_user_can_reverse_entry = can_reverse
            move.bks_user_can_draft_entry = can_draft

    def _bks_entry_button_acl_moves(self):
        """Pièces comptables hors facture, hors écritures paiement / relevé."""
        if self.env.su or self.env.context.get("bks_skip_entry_button_acl"):
            return self.browse()
        return self.filtered(
            lambda move: move.move_type == "entry"
            and not move.origin_payment_id
            and not move.statement_line_id
            and not (
                "rmg_l10n_ma_is_cgnc_closing" in move._fields
                and move.rmg_l10n_ma_is_cgnc_closing
            )
        )

    def _bks_raise_if_missing_entry_group(self, xmlid, message):
        targets = self._bks_entry_button_acl_moves()
        if targets and not self._bks_user_has_entry_button_group(xmlid):
            raise UserError(message)

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
        self._bks_raise_if_missing_entry_group(
            _BKS_ENTRY_POST_GROUP,
            _(
                "La comptabilisation d'une pièce comptable est réservée au "
                "groupe « Comptabiliser les pièces comptables »."
            ),
        )
        return super().action_post()

    def action_validate_moves_with_confirmation(self):
        self._bks_raise_if_missing_entry_group(
            _BKS_ENTRY_POST_GROUP,
            _(
                "La comptabilisation d'une pièce comptable est réservée au "
                "groupe « Comptabiliser les pièces comptables »."
            ),
        )
        return super().action_validate_moves_with_confirmation()

    def button_draft(self):
        entries = self.filtered(lambda move: move.move_type == "entry")
        invoices = self - entries
        if entries:
            self._bks_raise_if_missing_entry_group(
                _BKS_ENTRY_DRAFT_GROUP,
                _(
                    "La remise en brouillon d'une pièce comptable est réservée "
                    "au groupe « Remettre en brouillon les pièces comptables »."
                ),
            )
        blocked = invoices.filtered(
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
        entries = self.filtered(lambda move: move.move_type == "entry")
        invoices = self - entries
        if entries:
            self._bks_raise_if_missing_entry_group(
                _BKS_ENTRY_REVERSE_GROUP,
                _(
                    "L'extourne d'une pièce comptable est réservée au groupe "
                    "« Extourner les pièces comptables »."
                ),
            )
        blocked = invoices.filtered(
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

    def _bks_ensure_operation_department_from_creator(self):
        """Alimente manual_id depuis le créateur (facture hors BDC/DA)."""
        for move in self:
            if move.move_type not in _VENDOR_BILL_MOVE_TYPES:
                continue
            if move.purchase_order_count:
                continue
            if move.bks_operation_department_manual_id or move.bks_operation_department_id:
                continue
            company = move.company_id or move.env.company
            user = move.create_uid or self.env.user
            department = move._bks_department_for_user(user, company)
            if department:
                move.bks_operation_department_manual_id = department

    @api.depends(
        "invoice_line_ids.purchase_line_id.order_id.bks_operation_department_id",
        "line_ids.purchase_line_id.order_id.bks_operation_department_id",
        "invoice_line_ids.purchase_line_id",
        "bks_operation_department_manual_id",
        "create_uid",
        "company_id",
        "move_type",
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
        vendor_bills = self.filtered(
            lambda move: move.move_type in _VENDOR_BILL_MOVE_TYPES
        )
        vendor_bills._bks_ensure_operation_department_from_creator()
        vendor_bills._compute_bks_operation_department_id()
        missing = self.filtered(
            lambda move: move.move_type in _VENDOR_BILL_MOVE_TYPES
            and not move.bks_operation_department_id
        )
        if missing:
            raise UserError(
                _(
                    "Impossible de déterminer l'unité opérationnelle sur cette "
                    "facture fournisseur (BDC/DA ou département de l'employé "
                    "créateur). La validation ne peut pas être lancée."
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
        if (
            "bks_operation_department_id" in vals
            and not vals.get("bks_operation_department_id")
            and not self.env.context.get("bks_allow_clear_operation_department")
        ):
            vals = dict(vals)
            vals.pop("bks_operation_department_id", None)
        res = super().write(vals)
        drafts = self.filtered(
            lambda move: move.state == "draft"
            and move.move_type in _VENDOR_BILL_MOVE_TYPES
            and not move.bks_operation_department_id
        )
        if drafts:
            drafts._bks_ensure_operation_department_from_creator()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            move_type = vals.get("move_type") or self.env.context.get(
                "default_move_type"
            )
            if move_type in _VENDOR_BILL_MOVE_TYPES:
                self.env["purchase.order"]._bks_check_can_create_vendor_bill()
                break
        moves = super().create(vals_list)
        vendor_bills = moves.filtered(
            lambda move: move.move_type in _VENDOR_BILL_MOVE_TYPES
        )
        vendor_bills._bks_ensure_operation_department_from_creator()
        vendor_bills._compute_bks_operation_department_id()
        return moves
