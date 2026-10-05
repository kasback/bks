# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref(
        "purchase_request_tier_validation.group_coordonnateur",
        raise_if_not_found=False,
    )
    if not group:
        return
    manager = env.ref(
        "purchase_request.group_purchase_request_manager",
        raise_if_not_found=False,
    )
    user = env.ref(
        "purchase_request.group_purchase_request_user",
        raise_if_not_found=False,
    )
    commands = []
    if manager and manager in group.implied_ids:
        commands.append((3, manager.id))
    if user and user not in group.implied_ids:
        commands.append((4, user.id))
    if commands:
        group.write({"implied_ids": commands})
