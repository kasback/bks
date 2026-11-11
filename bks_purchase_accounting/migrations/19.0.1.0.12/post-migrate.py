def migrate(cr, version):
    import odoo

    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    group = env.ref(
        "bks_purchase_accounting.group_bks_partner_vendor_accounts",
        raise_if_not_found=False,
    )
    if not group:
        return
    accounting_groups = env.ref("account.group_account_user") | env.ref(
        "account.group_account_manager"
    )
    users = env["res.users"].search([("group_ids", "in", accounting_groups.ids)])
    group.user_ids = [(4, user_id) for user_id in users.ids]
