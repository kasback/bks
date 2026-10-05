# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

_BKS_ARCHIVE_SEQUENCE_STRIDE = 1000


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    Review = env["tier.review"].sudo()
    for model_name, table in (
        ("purchase.request", "purchase_request"),
        ("purchase.order", "purchase_order"),
    ):
        if model_name not in env:
            continue
        cr.execute(
            """
            SELECT DISTINCT res_id
            FROM tier_review
            WHERE model = %s AND status = 'cancel'
            """,
            (model_name,),
        )
        for (doc_id,) in cr.fetchall():
            cancelled = Review.search(
                [
                    ("model", "=", model_name),
                    ("res_id", "=", doc_id),
                    ("status", "=", "cancel"),
                    ("sequence", "<", _BKS_ARCHIVE_SEQUENCE_STRIDE),
                ],
                order="sequence, id",
            )
            if not cancelled:
                continue
            cr.execute(
                f"SELECT bks_tier_archive_wave FROM {table} WHERE id = %s",
                (doc_id,),
            )
            row = cr.fetchone()
            if not row:
                continue
            wave = max(row[0] or 0, 1)
            for review in cancelled:
                base_seq = review.sequence if review.sequence > 0 else 1
                review.sequence = wave * _BKS_ARCHIVE_SEQUENCE_STRIDE + base_seq
            cr.execute(
                f"""
                UPDATE {table}
                SET bks_tier_archive_wave = GREATEST(COALESCE(bks_tier_archive_wave, 0), %s)
                WHERE id = %s
                """,
                (wave, doc_id),
            )
