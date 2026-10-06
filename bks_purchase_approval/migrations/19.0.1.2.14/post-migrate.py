# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Retire l'attribution automatique : envoi email = groupe explicite."""
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in (
        "bks_purchase_approval.group_bks_send_ddp",
        "bks_purchase_approval.group_bks_send_bdc",
    ):
        group = env.ref(xmlid, raise_if_not_found=False)
        if group and group.user_ids:
            group.write({"user_ids": [(5, 0, 0)]})
            _logger.info(
                "bks_purchase_approval 19.0.1.2.14: membres retirés du groupe %s.",
                group.name,
            )
