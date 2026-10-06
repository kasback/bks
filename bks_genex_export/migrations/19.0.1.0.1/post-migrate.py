# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).


def migrate(cr, version):
    """Type EC Odoo → 563 sur les sociétés encore à 500 (valeur initiale)."""
    cr.execute(
        """
        UPDATE res_company
           SET genex_ec_type = 563
         WHERE genex_ec_type IS NULL OR genex_ec_type = 500
        """
    )
