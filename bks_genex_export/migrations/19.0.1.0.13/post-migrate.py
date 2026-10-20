# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).


def migrate(cr, version):
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS bks_genex_export_wizard_payment_rel (
            wizard_id INTEGER NOT NULL
                REFERENCES bks_genex_export_wizard(id) ON DELETE CASCADE,
            payment_id INTEGER NOT NULL
                REFERENCES account_payment(id) ON DELETE CASCADE,
            PRIMARY KEY (wizard_id, payment_id)
        )
        """
    )
