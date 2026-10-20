# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    """Retire le mixin supprimé qui provoquait des ir.model.inherit invalides."""
    cr.execute(
        """
        DELETE FROM ir_model_inherit
         WHERE model_id IN (
               SELECT id FROM ir_model
                WHERE model = 'bks.ma.payment.method.sync.mixin'
           )
            OR parent_id IN (
               SELECT id FROM ir_model
                WHERE model = 'bks.ma.payment.method.sync.mixin'
           )
        """
    )
    cr.execute(
        "DELETE FROM ir_model WHERE model = 'bks.ma.payment.method.sync.mixin'"
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE model = 'ir.model'
           AND name LIKE '%bks_ma_payment_method_sync_mixin%'
        """
    )
