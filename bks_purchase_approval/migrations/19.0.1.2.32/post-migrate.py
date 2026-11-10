def migrate(cr, version):
    import odoo

    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    moves = env["account.move"].search(
        [
            ("move_type", "in", ("in_invoice", "in_refund", "in_receipt")),
            ("state", "=", "draft"),
            ("bks_operation_department_id", "=", False),
        ]
    )
    moves._bks_ensure_operation_department_from_creator()
    moves._compute_bks_operation_department_id()
