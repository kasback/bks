# Copyright 2019-2020 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import UserError


class PurchaseRequest(models.Model):
    _name = "purchase.request"
    _inherit = ["purchase.request", "tier.validation"]
    _state_from = ["draft"]
    _state_to = ["approved"]

    _tier_validation_manual_config = False

    requested_by = fields.Many2one(
        string="Demandeur (Ordonnateur)",
    )
    assigned_to = fields.Many2one(
        string="Approbateur",
        compute="_compute_assigned_to",
        store=True,
        readonly=True,
        precompute=True,
        domain="[('share', '=', False)]",
        help="Renseigné automatiquement avec le supérieur hiérarchique "
        "de la fiche employé du demandeur.",
    )

    _BKS_LOCK_VALIDATION_STATUSES = frozenset(
        {"waiting", "pending", "validated", "rejected"}
    )

    name = fields.Char(
        default=False,
        readonly=True,
    )
    is_name_editable = fields.Boolean(
        compute="_compute_is_name_editable",
        default=False,
    )
    bks_can_request_pr_validation = fields.Boolean(
        compute="_compute_bks_can_request_pr_validation",
    )

    @api.depends("requested_by")
    @api.depends_context("uid")
    def _compute_bks_can_request_pr_validation(self):
        user = self.env.user
        is_ordonnateur = user.has_group(
            "purchase_request_tier_validation.group_ordonnateur"
        )
        is_responsable = user.has_group(
            "purchase_request_tier_validation.group_responsable_achats"
        )
        for rec in self:
            rec.bks_can_request_pr_validation = (
                is_ordonnateur
                or is_responsable
                or rec.requested_by == user
            )

    @api.depends()
    def _compute_is_name_editable(self):
        for rec in self:
            rec.is_name_editable = False

    @api.depends("state", "validation_status")
    def _compute_is_editable(self):
        super()._compute_is_editable()
        for rec in self:
            if rec.validation_status in self._BKS_LOCK_VALIDATION_STATUSES:
                rec.is_editable = False

    @api.model
    def _get_under_validation_exceptions(self):
        res = super()._get_under_validation_exceptions()
        res.append("route_id")
        return res

    def _get_requester_manager_user(self):
        """Return the user linked to the requester's hierarchical manager."""
        self.ensure_one()
        user = self.requested_by
        if not user:
            return self.env["res.users"]
        company = self.company_id or self.env.company
        employee = user.sudo().with_company(company).employee_id
        if not employee:
            employee = (
                self.env["hr.employee"]
                .sudo()
                .search(
                    [
                        ("user_id", "=", user.id),
                        "|",
                        ("company_id", "=", False),
                        ("company_id", "=", company.id),
                    ],
                    limit=1,
                )
            )
        return employee.parent_id.user_id

    @api.depends("requested_by", "company_id")
    def _compute_assigned_to(self):
        for rec in self:
            rec.assigned_to = rec._get_requester_manager_user()

    @api.model_create_multi
    def create(self, vals_list):
        cleaned = []
        new_labels = {self.env._("New"), "New", "Nouveau"}
        for vals in vals_list:
            vals = {k: v for k, v in vals.items() if k != "assigned_to"}
            if not vals.get("name") or vals.get("name") in new_labels:
                vals["name"] = self._get_default_name()
            cleaned.append(vals)
        return super().create(cleaned)

    def write(self, vals):
        if "assigned_to" in vals:
            vals = {k: v for k, v in vals.items() if k != "assigned_to"}
        if "name" in vals:
            vals = {k: v for k, v in vals.items() if k != "name"}
        return super().write(vals)

    def request_validation(self):
        for rec in self:
            if rec.requested_by and not rec.assigned_to:
                raise UserError(
                    self.env._(
                        "Aucun supérieur hiérarchique n'est défini sur la "
                        "fiche employé de %(user)s, ou ce supérieur n'a pas "
                        "d'utilisateur lié. Mettez à jour la fiche employé "
                        "avant de demander la validation.",
                        user=rec.requested_by.display_name,
                    )
                )
        return super().request_validation()
