# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    moves = env["account.move"].search(
        [("move_type", "in", ("in_invoice", "in_refund", "in_receipt"))]
    )
    if moves:
        moves._compute_bks_operation_department_id()
