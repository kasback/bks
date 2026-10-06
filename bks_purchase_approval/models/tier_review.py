# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models

_BKS_COORD_TIER_MODELS = frozenset(
    {"purchase.order", "purchase.request", "account.move"}
)


class TierReview(models.Model):
    _inherit = "tier.review"

    @api.model
    def _bks_user_matches_operation_department(self, user, department):
        """Même périmètre que les règles ir.rule co-ordonnateur."""
        if not department:
            return False
        if department.manager_id.user_id == user:
            return True
        employee = user.sudo().employee_id
        if not employee or not employee.department_id:
            return False
        allowed = self.env["hr.department"].search(
            [("id", "child_of", employee.department_id.ids)]
        )
        return department in allowed

    def _bks_filter_coordonnateur_reviewers(self, reviewers, resource):
        coord_group = self.env.ref(
            "purchase_request_tier_validation.group_coordonnateur",
            raise_if_not_found=False,
        )
        if (
            not coord_group
            or self.reviewer_group_id != coord_group
            or self.model not in _BKS_COORD_TIER_MODELS
        ):
            return reviewers
        department = resource.bks_operation_department_id
        if not department:
            return self.env["res.users"]
        return reviewers.filtered(
            lambda user: self._bks_user_matches_operation_department(user, department)
        )

    def _get_reviewers(self):
        reviewers = super()._get_reviewers()
        if self.model not in _BKS_COORD_TIER_MODELS:
            return reviewers
        resource = self.env[self.model].browse(self.res_id).exists()
        if not resource:
            return reviewers
        return self._bks_filter_coordonnateur_reviewers(reviewers, resource)

    @api.model_create_multi
    def create(self, vals_list):
        reviews = super().create(vals_list)
        reviews._compute_reviewer_ids()
        return reviews

    def _update_review_status(self):
        pending_reviews = self.filtered(
            lambda rev: rev.status in ("waiting", "pending")
        )
        if pending_reviews:
            pending_reviews._compute_reviewer_ids()
        return super()._update_review_status()

    def _notify_pending_status(self, review_ids):
        review_ids._compute_reviewer_ids()
        return super()._notify_pending_status(review_ids)

    @api.depends("reviewer_ids")
    def _compute_todo_by(self):
        super()._compute_todo_by()
        coord_group = self.env.ref(
            "purchase_request_tier_validation.group_coordonnateur",
            raise_if_not_found=False,
        )
        if not coord_group:
            return
        num_show = 3
        for rec in self.filtered(
            lambda review: review.reviewer_group_id == coord_group
            and review.model in _BKS_COORD_TIER_MODELS
        ):
            if not rec.reviewer_ids:
                rec.todo_by = self.env._(
                    "Aucun co-ordonnateur pour cette unité opérationnelle"
                )
                continue
            todo_by = ", ".join(rec.reviewer_ids[:num_show].mapped("display_name"))
            if len(rec.reviewer_ids) > num_show:
                todo_by = self.env._(
                    "%(names)s (et %(more)s autres)",
                    names=todo_by,
                    more=len(rec.reviewer_ids) - num_show,
                )
            rec.todo_by = todo_by
