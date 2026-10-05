# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in (
        "purchase_request_tier_validation.purchase_request_coordonnateur_reviewer_rule",
        "purchase_request_tier_validation.purchase_request_line_coordonnateur_reviewer_rule",
    ):
        rule = env.ref(xmlid, raise_if_not_found=False)
        if rule:
            rule.unlink()
    env["purchase.request"].search([])._compute_bks_operation_department_id()
