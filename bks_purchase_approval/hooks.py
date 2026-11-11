# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

_SALE_PURCHASE_MODULE = "sale_purchase"
_SALE_PO_VIEW_XMLID = "sale_purchase_stock.purchase_order_form_sale_purchase_stock"


def _sync_sale_purchase_stock_po_view(env):
    """Désactive la vue sale_purchase_stock si sale_purchase est absent.

    Le readonly ``dest_address_id`` utilise ``bks_has_sale_order`` (vue
    priorité 50) au lieu du ``has_sale_order`` standard réservé aux vendeurs.
    """
    sale_purchase_installed = bool(
        env["ir.module.module"].search_count(
            [
                ("name", "=", _SALE_PURCHASE_MODULE),
                ("state", "=", "installed"),
            ]
        )
    )
    view = env.ref(_SALE_PO_VIEW_XMLID, raise_if_not_found=False)
    if not view:
        return
    if view.active != sale_purchase_installed:
        view.active = sale_purchase_installed


def post_init_hook(env):
    _sync_sale_purchase_stock_po_view(env)
