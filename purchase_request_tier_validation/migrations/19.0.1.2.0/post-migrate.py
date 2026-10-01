def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    requested_by = env.ref(
        "purchase_request.field_purchase_request__requested_by",
        raise_if_not_found=False,
    )
    assigned_to = env.ref(
        "purchase_request.field_purchase_request__assigned_to",
        raise_if_not_found=False,
    )
    if not requested_by or not assigned_to:
        return

    ordonnateur = env.ref(
        "purchase_request_tier_validation.tier_da_signature_ordonnateur",
        raise_if_not_found=False,
    )
    if ordonnateur:
        ordonnateur.write(
            {
                "name": "DA - Signature Ordonnateur (demandeur)",
                "review_type": "field",
                "reviewer_id": False,
                "reviewer_group_id": False,
                "reviewer_field_id": requested_by.id,
            }
        )

    manager_tier = env.ref(
        "purchase_request_tier_validation.tier_da_signature_coordonnateur",
        raise_if_not_found=False,
    )
    if manager_tier:
        manager_tier.write(
            {
                "name": "DA - Signature supérieur hiérarchique",
                "review_type": "field",
                "reviewer_id": False,
                "reviewer_group_id": False,
                "reviewer_field_id": assigned_to.id,
            }
        )
