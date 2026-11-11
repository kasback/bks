def migrate(cr, version):
    import odoo

    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    from odoo.addons.bks_purchase_approval.hooks import _sync_sale_purchase_stock_po_view

    _sync_sale_purchase_stock_po_view(env)
