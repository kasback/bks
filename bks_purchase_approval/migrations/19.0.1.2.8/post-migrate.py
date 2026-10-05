# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

_logger = logging.getLogger(__name__)

_PURCHASE_PROFILE_GROUP_XMLIDS = (
    "purchase_request_tier_validation.group_ordonnateur",
    "purchase_request_tier_validation.group_coordonnateur",
    "purchase_request_tier_validation.group_acheteur",
    "purchase_request_tier_validation.group_responsable_achats",
    "purchase_request_tier_validation.group_directeur_pole",
    "purchase_request_tier_validation.group_president",
)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    finance_group = env.ref(
        "bks_purchase_approval.group_bks_finance_move_credit_draft",
        raise_if_not_found=False,
    )
    if not finance_group:
        return

    accounting_users = (
        env.ref("account.group_account_manager").user_ids
        | env.ref("account.group_account_invoice").user_ids
    )
    purchase_group_ids = {
        env.ref(xmlid).id
        for xmlid in _PURCHASE_PROFILE_GROUP_XMLIDS
        if env.ref(xmlid, raise_if_not_found=False)
    }

    def _is_direction_financiere(user):
        if user not in accounting_users:
            return False
        if purchase_group_ids.intersection(user.group_ids.ids):
            return False
        return True

    eligible = accounting_users.filtered(_is_direction_financiere)
    if eligible:
        finance_group.write({"user_ids": [(4, uid) for uid in eligible.ids]})
        _logger.info(
            "bks_purchase_approval 19.0.1.2.8: groupe Avoir/brouillon "
            "attribué à %s utilisateur(s) direction financière.",
            len(eligible),
        )
