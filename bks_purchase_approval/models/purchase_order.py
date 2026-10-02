# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    bks_operation_department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Unité opérationnelle (DA)",
        compute="_compute_bks_operation_department_id",
        store=True,
        help="Département du demandeur (ordonnateur) sur les DA liées à ce BDC.",
    )

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

    @api.model
    def _get_under_validation_exceptions(self):
        exceptions = super()._get_under_validation_exceptions()
        exceptions.append("bks_operation_department_id")
        return exceptions
