# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseRequest(models.Model):
    _inherit = "purchase.request"

    bks_operation_department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Unité opérationnelle",
        compute="_compute_bks_operation_department_id",
        store=True,
        readonly=True,
        help="Département du demandeur (ordonnateur) sur la demande d'achat.",
    )

    @api.depends("requested_by", "company_id")
    def _compute_bks_operation_department_id(self):
        Employee = self.env["hr.employee"].sudo()
        for request in self:
            department = self.env["hr.department"]
            company = request.company_id or request.env.company
            user = request.requested_by
            if user:
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
            request.bks_operation_department_id = department
        self._bks_refresh_coordonnateur_reviewers()

    def request_validation(self):
        for request in self:
            lines_without_product = request.line_ids.filtered(lambda line: not line.product_id)
            if lines_without_product:
                raise UserError(
                    _(
                        "Impossible de demander la validation : chaque ligne "
                        "de la demande d'achat doit avoir un article."
                    )
                )
        return super().request_validation()
