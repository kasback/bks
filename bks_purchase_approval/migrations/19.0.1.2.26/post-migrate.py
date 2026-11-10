# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    post_group = env.ref(
        "bks_purchase_approval.group_bks_entry_post",
        raise_if_not_found=False,
    )
    reverse_group = env.ref(
        "bks_purchase_approval.group_bks_entry_reverse",
        raise_if_not_found=False,
    )
    draft_group = env.ref(
        "bks_purchase_approval.group_bks_entry_draft",
        raise_if_not_found=False,
    )
    finance_group = env.ref(
        "bks_purchase_approval.group_bks_finance_move_credit_draft",
        raise_if_not_found=False,
    )
    if not (post_group and reverse_group and draft_group):
        return

    users = env["res.users"].search([("share", "=", False), ("active", "=", True)])
    accountants = users.filtered(
        lambda user: user.has_group("account.group_account_invoice")
    )
    if accountants:
        post_group.write({"user_ids": [(4, uid) for uid in accountants.ids]})
        reverse_group.write({"user_ids": [(4, uid) for uid in accountants.ids]})
        _logger.info(
            "bks_purchase_approval 19.0.1.2.26: Comptabiliser/Extourner "
            "pièces attribué à %s utilisateur(s) comptabilité.",
            len(accountants),
        )

    draft_users = accountants
    if finance_group:
        draft_users = users.filtered(
            lambda user: user.has_group(
                "bks_purchase_approval.group_bks_finance_move_credit_draft"
            )
        )
    if draft_users:
        draft_group.write({"user_ids": [(4, uid) for uid in draft_users.ids]})
        _logger.info(
            "bks_purchase_approval 19.0.1.2.26: Remise en brouillon pièces "
            "attribué à %s utilisateur(s).",
            len(draft_users),
        )
