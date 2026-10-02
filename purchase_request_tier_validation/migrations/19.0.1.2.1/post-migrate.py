# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    cr.execute(
        """
        UPDATE res_groups g
        SET privilege_id = NULL
        FROM ir_model_data d
        WHERE d.model = 'res.groups'
          AND d.module = 'purchase_request_tier_validation'
          AND d.name IN (
              'group_bks_tier_restart_validation',
              'group_bks_da_reset'
          )
          AND g.id = d.res_id
        """
    )
