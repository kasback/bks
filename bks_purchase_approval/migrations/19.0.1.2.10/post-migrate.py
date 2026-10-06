# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    configs = (
        ("purchase.request", "Unité opérationnelle (DA)"),
        ("purchase.order", "Unité opérationnelle (DA)"),
        ("account.move", "Unité opérationnelle (DA)"),
    )
    Exception = env["tier.validation.exception"]
    Field = env["ir.model.fields"]
    for model_name, label in configs:
        field = Field.search(
            [("model", "=", model_name), ("name", "=", "bks_operation_department_id")],
            limit=1,
        )
        if not field:
            continue
        model = env["ir.model"].search([("model", "=", model_name)], limit=1)
        if not model:
            continue
        exists = Exception.search(
            [
                ("model_id", "=", model.id),
                ("field_ids", "in", field.id),
            ],
            limit=1,
        )
        if exists:
            continue
        Exception.create(
            {
                "name": label,
                "model_id": model.id,
                "field_ids": [(6, 0, field.ids)],
                "allowed_to_write_under_validation": True,
                "allowed_to_write_after_validation": True,
            }
        )

    for model_name in ("purchase.request", "purchase.order", "account.move"):
        if model_name not in env:
            continue
        env[model_name].with_context(skip_validation_check=True).search(
            []
        )._compute_bks_operation_department_id()
