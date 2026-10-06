# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Un seul palier paiement : désactive les autres définitions tier account.payment."""
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    payment_model = env.ref("account.model_account_payment", raise_if_not_found=False)
    our_tier = env.ref(
        "account_payment_tier_validation.tier_payment_validation_responsable_reglement",
        raise_if_not_found=False,
    )
    if not payment_model:
        return
    domain = [("model_id", "=", payment_model.id)]
    if our_tier:
        domain.append(("id", "!=", our_tier.id))
    others = env["tier.definition"].search(domain)
    if others:
        others.write({"active": False})
        _logger.info(
            "account_payment_tier_validation 19.0.1.0.3: %s palier(s) paiement "
            "désactivé(s) (conservation du Responsable de règlement).",
            len(others),
        )
