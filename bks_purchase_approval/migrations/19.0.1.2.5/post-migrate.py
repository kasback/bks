# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    coord = env.ref(
        "purchase_request_tier_validation.group_coordonnateur",
        raise_if_not_found=False,
    )
    if not coord:
        return
    reviews = env["tier.review"].search(
        [
            ("model", "in", ("purchase.order", "purchase.request")),
            ("status", "in", ("waiting", "pending")),
            ("reviewer_group_id", "=", coord.id),
        ]
    )
    if reviews:
        reviews._compute_reviewer_ids()
