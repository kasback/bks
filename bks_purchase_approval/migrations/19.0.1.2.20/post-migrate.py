# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    exception = env.ref(
        "bks_purchase_approval.tier_validation_exception_move_operation_unit",
        raise_if_not_found=False,
    )
    manual_field = env.ref(
        "bks_purchase_approval.field_account_move__bks_operation_department_manual_id",
        raise_if_not_found=False,
    )
    if exception and manual_field and manual_field not in exception.field_ids:
        exception.write({"field_ids": [(4, manual_field.id)]})
