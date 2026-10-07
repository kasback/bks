# pylint: disable=invalid-commit


def migrate(cr, version):
    cr.execute(
        """
        UPDATE account_payment pay
           SET genex_exported = move.genex_exported,
               genex_export_date = move.genex_export_date,
               genex_export_user_id = move.genex_export_user_id
          FROM account_move move
         WHERE pay.move_id = move.id
           AND move.genex_exported IS TRUE
           AND (pay.genex_exported IS NOT TRUE OR pay.genex_exported IS NULL)
        """
    )
