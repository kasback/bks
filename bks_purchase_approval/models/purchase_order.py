# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext
from odoo.tools.misc import file_path

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
    bks_has_sale_order = fields.Boolean(
        string="BC lié à une vente (technique)",
        compute="_compute_bks_has_sale_order",
    )

    @api.depends("order_line.sale_line_id")
    def _compute_bks_has_sale_order(self):
        line_model = self.env["purchase.order.line"]
        if "sale_line_id" not in line_model._fields:
            for order in self:
                order.bks_has_sale_order = False
            return
        for order in self:
            order.bks_has_sale_order = any(
                line.sale_line_id for line in order.order_line
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

    def _bks_po_print_lines(self):
        self.ensure_one()
        lines = self.order_line.filtered(
            lambda line: not line.display_type and line.product_qty
        )
        if "is_downpayment" in lines._fields:
            lines = lines.filtered(lambda line: not line.is_downpayment)
        return lines

    def _bks_po_print_logo(self):
        self.ensure_one()
        if self.company_id.logo:
            return self.company_id.logo
        try:
            logo_path = file_path(
                "bks_purchase_approval/static/src/img/logo_bank_assafa.png"
            )
        except (FileNotFoundError, OSError, ValueError):
            return False
        with open(logo_path, "rb") as logo_file:
            return base64.b64encode(logo_file.read())

    def _bks_po_print_city(self):
        self.ensure_one()
        company = self.company_id
        return company.city or company.partner_id.city or "Casablanca"

    def _bks_po_print_date(self):
        self.ensure_one()
        raw = self.date_approve or self.date_order
        if not raw:
            return fields.Date.context_today(self)
        return fields.Datetime.context_timestamp(self, raw).date()

    def _bks_po_print_objet(self):
        self.ensure_one()
        note = html2plaintext(self.note or "").strip()
        if note:
            subject = note.splitlines()[0].strip()
        else:
            line = self._bks_po_print_lines()[:1]
            subject = ""
            if line:
                subject = (line.name or line.product_id.display_name or "").splitlines()[
                    0
                ].strip()
            subject = subject or self.origin or ""
        dept = self.bks_operation_department_id.name
        if dept and dept.lower() not in (subject or "").lower():
            if subject:
                subject = f"{subject} - Au profit du département {dept}"
            else:
                subject = f"Au profit du département {dept}"
        return subject

    def _bks_po_print_delivery_date(self):
        self.ensure_one()
        planned = self.date_planned
        if not planned:
            return _("Immédiat")
        planned_date = planned.date() if hasattr(planned, "date") else planned
        today = fields.Date.context_today(self)
        if planned_date <= today:
            return _("Immédiat")
        return planned_date.strftime("%d/%m/%Y")

    def _bks_po_print_delivery_place(self):
        self.ensure_one()
        partner = self.dest_address_id
        if not partner and self.picking_type_id.warehouse_id.partner_id:
            partner = self.picking_type_id.warehouse_id.partner_id
        if partner and partner != self.company_id.partner_id:
            parts = [
                partner.name,
                partner.street,
                partner.street2,
                " ".join(p for p in (partner.zip, partner.city) if p),
            ]
            text = ", ".join(p for p in parts if p)
            if text:
                return text
        return _("Siège %s", self.company_id.name)

    def _bks_po_print_signatories(self):
        self.ensure_one()
        buyer = self.user_id
        left_name = buyer.name or ""
        left_title = _("Responsable Achat")
        right_name = ""
        right_title = _("Responsable LAPS")
        employee = buyer.with_company(self.company_id).employee_id
        manager = employee.parent_id or employee.department_id.manager_id
        if manager and manager.name and manager.name != left_name:
            right_name = manager.name
        return left_name, left_title, right_name, right_title

    def _bks_po_print_data(self):
        self.ensure_one()
        print_date = self._bks_po_print_date()
        city = self._bks_po_print_city()
        lines = self._bks_po_print_lines()
        left_name, left_title, right_name, right_title = self._bks_po_print_signatories()
        closing = _(
            "Veuillez agréer, Madame, Monsieur, l'expression de nos salutations distinguées."
        )
        return {
            "logo": self._bks_po_print_logo(),
            "city_date": _("%(city)s, le %(date)s", city=city, date=print_date.strftime("%d/%m/%Y")),
            "partner_name": self.partner_id.name or "",
            "partner_city": (self.partner_id.city or "").title()
            if self.partner_id.city
            else "",
            "service": "LAPS",
            "title": _("Bon de Commande"),
            "objet": self._bks_po_print_objet(),
            "reference": self.name or "",
            "intro": _(
                "Nous avons le plaisir de vous passer commande pour la prestation suivante :"
            ),
            "lines": [
                {
                    "name": line.name or "",
                    "qty": line.product_qty,
                    "price_unit": line.price_unit,
                    "price_subtotal": line.price_subtotal,
                }
                for line in lines
            ],
            "amount_untaxed": sum(lines.mapped("price_subtotal")),
            "currency": self.currency_id,
            "comment_title": _("Commentaires"),
            "comment": _(
                "* La facture doit être déposée au maximum 15 jours après "
                "réalisation de la prestation, toute pénalité réglée par la "
                "banque à cause du retard de dépôt de la facture par le "
                "prestataire sera imputée sur le règlement des prochaines "
                "factures en cours."
            ),
            "conditions_title": _("Avec les conditions suivantes:"),
            "delivery_date": self._bks_po_print_delivery_date(),
            "delivery_place": self._bks_po_print_delivery_place(),
            "closing": closing,
            "sign_left_name": left_name,
            "sign_left_title": left_title,
            "sign_right_name": right_name,
            "sign_right_title": right_title,
        }

