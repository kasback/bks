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
        readonly=False,
        precompute=True,
        domain="[('share', '=', False)]",
        help="Renseigné automatiquement avec le supérieur hiérarchique "
        "de la fiche employé du demandeur.",
    )

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
