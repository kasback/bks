# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_BKS_VENDOR_BILL_CREATOR_GROUPS = (
    "base.group_system",
    "account.group_account_invoice",
    "account.group_account_manager",
    "purchase_request_tier_validation.group_responsable_achats",
)
_BKS_SEND_BDC_GROUP = "bks_purchase_approval.group_bks_send_bdc"
_BKS_SEND_DDP_GROUP = "bks_purchase_approval.group_bks_send_ddp"


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    bks_can_create_vendor_bill = fields.Boolean(
        compute="_compute_bks_can_create_vendor_bill",
    )
    bks_can_send_ddp = fields.Boolean(
        compute="_compute_bks_po_email_access",
    )
    bks_can_send_bdc_email = fields.Boolean(
        compute="_compute_bks_po_email_access",
    )
    bks_operation_department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Unité opérationnelle (DA)",
        compute="_compute_bks_operation_department_id",
        store=True,
        readonly=True,
        help="Département du demandeur (ordonnateur) sur les DA liées à ce BDC.",
    )

    @api.model
    def _bks_user_can_create_vendor_bill(self):
        user = self.env.user
        return any(user.has_group(xmlid) for xmlid in _BKS_VENDOR_BILL_CREATOR_GROUPS)

    @api.model
    def _bks_check_can_create_vendor_bill(self):
        if not self._bks_user_can_create_vendor_bill():
            raise UserError(
                _(
                    "La création de factures fournisseur est réservée aux "
                    "profils Comptabilité fournisseurs ou Responsable Achats."
                )
            )

    @api.depends_context("uid")
    def _compute_bks_can_create_vendor_bill(self):
        can = self._bks_user_can_create_vendor_bill()
        for order in self:
            order.bks_can_create_vendor_bill = can

    @api.depends_context("uid")
    def _compute_bks_po_email_access(self):
        user = self.env.user
        can_ddp = user.has_group(_BKS_SEND_DDP_GROUP)
        can_bdc = user.has_group(_BKS_SEND_BDC_GROUP)
        for order in self:
            order.bks_can_send_ddp = can_ddp
            order.bks_can_send_bdc_email = can_bdc

    @api.model
    def _bks_check_can_send_ddp_email(self):
        if not self.env.user.has_group(_BKS_SEND_DDP_GROUP):
            raise UserError(
                _(
                    "L'envoi de la demande de prix par email est réservé aux "
                    "utilisateurs du groupe « Envoyer une demande de prix »."
                )
            )

    @api.model
    def _bks_check_can_send_bdc_email(self):
        if not self.env.user.has_group(_BKS_SEND_BDC_GROUP):
            raise UserError(
                _(
                    "L'envoi du bon de commande par email est réservé aux "
                    "utilisateurs du groupe « Envoyer un bon de commande »."
                )
            )

    def action_rfq_send(self):
        if self.env.context.get("send_rfq", False):
            self._bks_check_can_send_ddp_email()
        else:
            self._bks_check_can_send_bdc_email()
        return super().action_rfq_send()

    def action_create_invoice(self, attachment_ids=False):
        self._bks_check_can_create_vendor_bill()
        return super().action_create_invoice(attachment_ids=attachment_ids)

    def _deduct_payment(self, grouped=False, final=False, date=None):
        self._bks_check_can_create_vendor_bill()
        return super()._deduct_payment(grouped=grouped, final=final, date=date)

    @api.depends(
        "order_line.purchase_request_lines.request_id.requested_by",
        "order_line.purchase_request_lines.request_id.company_id",
        "company_id",
    )
    def _compute_bks_operation_department_id(self):
        Employee = self.env["hr.employee"].sudo()
        for order in self:
            department = self.env["hr.department"]
            company = order.company_id or order.env.company
            requesters = order.order_line.purchase_request_lines.request_id.mapped(
                "requested_by"
            )
            for user in requesters:
                employee = user.with_company(company).employee_id
                if not employee:
                    employee = Employee.search(
                        [
                            ("user_id", "=", user.id),
                            "|",
                            ("company_id", "=", False),
                            ("company_id", "=", company.id),
                        ],
                        limit=1,
                    )
                if employee.department_id:
                    department = employee.department_id
                    break
            order.bks_operation_department_id = department
        self._bks_refresh_coordonnateur_reviewers()
