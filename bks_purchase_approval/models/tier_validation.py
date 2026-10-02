# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.exceptions import AccessError, UserError
from odoo import api, fields, models
from odoo.tools.misc import frozendict

_BKS_TIER_FORM_MODELS = frozenset({"purchase.request", "purchase.order"})
_RESTART_GROUP_XMLID = (
    "purchase_request_tier_validation.group_bks_tier_restart_validation"
)
# Séquences 1–99 : circuit en cours ; paliers 1000+ : vagues archivées (annulées).
_BKS_ARCHIVE_SEQUENCE_STRIDE = 1000


class TierValidation(models.AbstractModel):
    _inherit = "tier.validation"

    review_ids = fields.One2many(
        comodel_name="tier.review",
        inverse_name="res_id",
        string="Validations",
        domain=lambda self: [
            ("model", "=", self._name),
            ("status", "!=", "cancel"),
        ],
        bypass_search_access=True,
    )
    tier_review_all_ids = fields.One2many(
        comodel_name="tier.review",
        inverse_name="res_id",
        string="Historique des validations",
        domain=lambda self: [("model", "=", self._name)],
        bypass_search_access=True,
    )

    bks_tier_archive_wave = fields.Integer(
        string="Vague d'archivage validation",
        default=0,
        copy=False,
        help="Compteur interne pour décaler les séquences des revues annulées.",
    )

    bks_can_restart_validation = fields.Boolean(
        compute="_compute_bks_can_restart_validation",
    )

    @api.depends_context("uid")
    def _compute_bks_can_restart_validation(self):
        can_restart = self.env.user.has_group(_RESTART_GROUP_XMLID)
        for record in self:
            record.bks_can_restart_validation = can_restart

    def _bks_can_restart_validation(self):
        return self.env.user.has_group(_RESTART_GROUP_XMLID)

    def restart_validation(self):
        if self._name in _BKS_TIER_FORM_MODELS:
            if not self._bks_can_restart_validation():
                raise AccessError(
                    self.env._(
                        "Seuls les utilisateurs du groupe "
                        "« Recommencer validation (tiers) » peuvent recommencer "
                        "la validation."
                    )
                )
            return self._bks_restart_validation_preserve_history()
        return super().restart_validation()

    def _bks_restart_validation_preserve_history(self):
        """Archive current reviews (status cancel) instead of deleting them."""
        for rec in self:
            state_field = rec._state_field
            if getattr(rec, state_field) not in rec._state_from:
                continue
            active_reviews = self.env["tier.review"].search(
                [
                    ("model", "=", rec._name),
                    ("res_id", "=", rec.id),
                    ("status", "!=", "cancel"),
                ]
            )
            if not active_reviews:
                continue
            partners_to_notify_ids = False
            to_update_counter = bool(
                active_reviews.filtered(lambda review: review.status in ("waiting", "pending"))
            )
            reviews_to_notify = active_reviews.filtered(
                lambda review: review.definition_id.notify_on_restarted
            )
            if reviews_to_notify:
                partners_to_notify_ids = (
                    reviews_to_notify.mapped("reviewer_ids")
                    .mapped("partner_id")
                    .ids
                )
            can_review = rec.can_review
            wave = rec.bks_tier_archive_wave + 1
            for review in active_reviews.sorted("sequence"):
                review.write(
                    {
                        "status": "cancel",
                        "sequence": wave * _BKS_ARCHIVE_SEQUENCE_STRIDE
                        + review.sequence,
                    }
                )
            rec.sudo().write({"bks_tier_archive_wave": wave})
            if to_update_counter and can_review:
                rec._update_counter({"review_deleted": True})
            if partners_to_notify_ids:
                subscribe = "message_subscribe"
                if hasattr(rec, subscribe):
                    getattr(rec, subscribe)(
                        partner_ids=partners_to_notify_ids,
                        subtype_ids=rec.env.ref(
                            rec._get_restarted_notification_subtype()
                        ).ids,
                    )
                rec._notify_restarted_review()

    def reject_tier(self):
        if self._name in _BKS_TIER_FORM_MODELS:
            raise UserError(
                self.env._("Le rejet n'est pas autorisé sur ce document.")
            )
        return super().reject_tier()

    def _bks_is_coordonnateur_only(self):
        """Co-ordonnateur sans rôle achats / ordonnateur / admin."""
        user = self.env.user
        if not user.has_group(
            "purchase_request_tier_validation.group_coordonnateur"
        ):
            return False
        privileged = (
            "purchase_request_tier_validation.group_responsable_achats",
            "purchase_request_tier_validation.group_acheteur",
            "purchase_request_tier_validation.group_ordonnateur",
            "purchase.group_purchase_manager",
            "base.group_system",
        )
        return not any(user.has_group(xmlid) for xmlid in privileged)

    def _bks_drop_buttons(self, doc, names):
        for name in names:
            for button in doc.xpath(f"//button[@name='{name}']"):
                parent = button.getparent()
                if parent is not None:
                    parent.remove(button)

    def _bks_patch_tier_form_arch(self, model_name, res):
        doc = etree.XML(res["arch"])
        if self._bks_is_coordonnateur_only():
            drop = [
                "restart_validation",
                "request_validation",
                "reject_tier",
                "button_draft",
                "button_done",
                "button_in_progress",
                "button_rejected",
                "button_approved",
                "button_to_approve",
                "button_confirm",
                "button_cancel",
                "button_approve",
                "action_rfq_send",
                "button_lock",
                "button_unlock",
                "action_acknowledge",
            ]
            self._bks_drop_buttons(doc, drop)
            for button in doc.xpath("//header/button[@type='action']"):
                parent = button.getparent()
                if parent is not None:
                    parent.remove(button)
        if not doc.xpath("//field[@name='bks_can_restart_validation']"):
            header = doc.xpath("//form/header")
            if header:
                field = etree.Element(
                    "field", name="bks_can_restart_validation", invisible="1"
                )
                header[0].insert(0, field)
        for button in doc.xpath("//button[@name='reject_tier']"):
            button.set("invisible", "1")
        if model_name == "purchase.request":
            for button in doc.xpath("//button[@name='request_validation']"):
                base_invisible = button.get("invisible") or "False"
                button.set(
                    "invisible",
                    f"({base_invisible}) or not bks_can_request_pr_validation",
                )
            if not doc.xpath("//field[@name='bks_can_request_pr_validation']"):
                header = doc.xpath("//form/header")
                if header:
                    field = etree.Element(
                        "field",
                        name="bks_can_request_pr_validation",
                        invisible="1",
                    )
                    header[0].insert(0, field)
        for button in doc.xpath("//button[@name='restart_validation']"):
            button.attrib.pop("groups", None)
            base_invisible = button.get("invisible") or "False"
            button.set(
                "invisible",
                f"({base_invisible}) or not bks_can_restart_validation",
            )
        for field in doc.xpath("//field[@widget='tier_validation']"):
            field.set("name", "tier_review_all_ids")
            field.set("invisible", "not tier_review_all_ids")
        res["arch"] = etree.tostring(doc, encoding="unicode")
        all_models = dict(res.get("models") or {})
        fields_tuple = tuple(all_models.get(model_name, ()))
        extra_fields = ["bks_can_restart_validation", "tier_review_all_ids"]
        if model_name == "purchase.request":
            extra_fields.append("bks_can_request_pr_validation")
        missing = [name for name in extra_fields if name not in fields_tuple]
        if missing:
            all_models[model_name] = fields_tuple + tuple(missing)
        res["models"] = frozendict(all_models)
        return res

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == "form" and self._name in _BKS_TIER_FORM_MODELS:
            res = self._bks_patch_tier_form_arch(self._name, res)
        return res
