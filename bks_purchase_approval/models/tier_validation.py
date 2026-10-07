# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.exceptions import AccessError
from odoo import api, fields, models
from odoo.tools.misc import frozendict

_BKS_TIER_FORM_MODELS = frozenset(
    {"purchase.request", "purchase.order", "account.payment", "account.move"}
)
_BKS_OPERATION_DEPARTMENT_MODELS = frozenset(
    {"purchase.request", "purchase.order", "account.move"}
)
_BKS_OPERATION_DEPARTMENT_FIELD = "bks_operation_department_id"
_BKS_COORD_GROUP_XMLID = "purchase_request_tier_validation.group_coordonnateur"
_BKS_RESTART_VALIDATION_CONFIRM = (
    "Recommencer la validation réinitialise le circuit en cours. "
    "Voulez-vous continuer ?"
)
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

    @api.model
    def _bks_append_operation_department_exceptions(self, field_names):
        if (
            self._name in _BKS_OPERATION_DEPARTMENT_MODELS
            and _BKS_OPERATION_DEPARTMENT_FIELD in self._fields
            and _BKS_OPERATION_DEPARTMENT_FIELD not in field_names
        ):
            field_names.append(_BKS_OPERATION_DEPARTMENT_FIELD)
        return field_names

    @api.model
    def _get_under_validation_exceptions(self):
        exceptions = super()._get_under_validation_exceptions()
        return self._bks_append_operation_department_exceptions(exceptions)

    @api.model
    def _get_after_validation_exceptions(self):
        exceptions = super()._get_after_validation_exceptions()
        return self._bks_append_operation_department_exceptions(exceptions)

    def write(self, vals):
        if (
            self._name in _BKS_OPERATION_DEPARTMENT_MODELS
            and vals
            and set(vals.keys()) <= {_BKS_OPERATION_DEPARTMENT_FIELD}
        ):
            return super(
                TierValidation, self.with_context(skip_validation_check=True)
            ).write(vals)
        return super().write(vals)

    def _bks_refresh_coordonnateur_reviewers(self):
        """Recalcule les validateurs co-ordonnateur après changement d'unité."""
        coord_group = self.env.ref(_BKS_COORD_GROUP_XMLID, raise_if_not_found=False)
        if not coord_group or self._name not in _BKS_OPERATION_DEPARTMENT_MODELS:
            return
        reviews = self.review_ids.filtered(
            lambda review: review.status in ("waiting", "pending")
            and review.reviewer_group_id == coord_group
        )
        if reviews:
            reviews._compute_reviewer_ids()

    def _notify_review_requested(self, tier_reviews):
        tier_reviews._compute_reviewer_ids()
        return super()._notify_review_requested(tier_reviews)

    def _notify_review_available(self, tier_reviews):
        tier_reviews._compute_reviewer_ids()
        return super()._notify_review_available(tier_reviews)

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

    def _bks_archive_active_tier_reviews(self, notify_restarted=False):
        """Conserve l'historique : statut cancel + décalage de séquence."""
        self.ensure_one()
        active_reviews = self.env["tier.review"].search(
            [
                ("model", "=", self._name),
                ("res_id", "=", self.id),
                ("status", "!=", "cancel"),
            ]
        )
        if not active_reviews:
            return
        partners_to_notify_ids = False
        to_update_counter = bool(
            active_reviews.filtered(
                lambda review: review.status in ("waiting", "pending")
            )
        )
        if notify_restarted:
            reviews_to_notify = active_reviews.filtered(
                lambda review: review.definition_id.notify_on_restarted
            )
            if reviews_to_notify:
                partners_to_notify_ids = (
                    reviews_to_notify.mapped("reviewer_ids")
                    .mapped("partner_id")
                    .ids
                )
        can_review = self.can_review
        wave = self.bks_tier_archive_wave + 1
        for review in active_reviews.sorted("sequence"):
            review.write(
                {
                    "status": "cancel",
                    "sequence": wave * _BKS_ARCHIVE_SEQUENCE_STRIDE
                    + review.sequence,
                }
            )
        self.sudo().with_context(skip_validation_check=True).write(
            {"bks_tier_archive_wave": wave}
        )
        if to_update_counter and can_review:
            self._update_counter({"review_deleted": True})
        if notify_restarted and partners_to_notify_ids:
            subscribe = "message_subscribe"
            if hasattr(self, subscribe):
                getattr(self, subscribe)(
                    partner_ids=partners_to_notify_ids,
                    subtype_ids=self.env.ref(
                        self._get_restarted_notification_subtype()
                    ).ids,
                )
            self._notify_restarted_review()

    def _bks_restart_validation_preserve_history(self):
        for rec in self:
            state_field = rec._state_field
            if getattr(rec, state_field) not in rec._state_from:
                continue
            rec._bks_archive_active_tier_reviews(notify_restarted=True)

    def _tier_validation_check_write_remove_reviews(self, vals):
        bks_records = self.filtered(lambda rec: rec._name in _BKS_TIER_FORM_MODELS)
        for rec in bks_records:
            if rec._allow_to_remove_reviews(vals):
                rec._bks_archive_active_tier_reviews(notify_restarted=False)
        other = self - bks_records
        if other:
            super(TierValidation, other)._tier_validation_check_write_remove_reviews(
                vals
            )

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

    def _bks_patch_po_send_email_buttons(self, doc):
        """Force la visibilité des envois email PO via groupes (get_view)."""
        if self._bks_is_coordonnateur_only():
            return
        header = doc.xpath("//form/header")
        if header:
            for fname in ("bks_can_send_ddp", "bks_can_send_bdc_email"):
                if not doc.xpath(f"//field[@name='{fname}']"):
                    header[0].insert(
                        0, etree.Element("field", name=fname, invisible="1")
                    )
        buttons = doc.xpath("//header/button[@name='action_rfq_send']")
        if len(buttons) >= 1:
            buttons[0].attrib.pop("groups", None)
            buttons[0].set(
                "invisible", "state != 'draft' or not bks_can_send_ddp"
            )
        if len(buttons) >= 2:
            buttons[1].attrib.pop("groups", None)
            buttons[1].set(
                "invisible", "state != 'sent' or not bks_can_send_ddp"
            )
        if len(buttons) >= 3:
            buttons[2].attrib.pop("groups", None)
            buttons[2].set(
                "invisible",
                "state != 'purchase' or not bks_can_send_bdc_email",
            )

    def _bks_patch_tier_form_arch(self, model_name, res):
        doc = etree.XML(res["arch"])
        if self._bks_is_coordonnateur_only():
            drop = [
                "restart_validation",
                "request_validation",
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
        if model_name == "purchase.order":
            self._bks_patch_po_send_email_buttons(doc)
        res["arch"] = etree.tostring(doc, encoding="unicode")
        all_models = dict(res.get("models") or {})
        fields_tuple = tuple(all_models.get(model_name, ()))
        extra_fields = ["bks_can_restart_validation", "tier_review_all_ids"]
        if model_name == "purchase.order":
            extra_fields.extend(
                [
                    "bks_can_send_ddp",
                    "bks_can_send_bdc_email",
                    "bks_can_create_vendor_bill",
                ]
            )
        if model_name == "purchase.request":
            extra_fields.extend(
                [
                    "bks_can_request_pr_validation",
                    "bks_can_create_rfq",
                    "bks_operation_department_id",
                ]
            )
        missing = [name for name in extra_fields if name not in fields_tuple]
        if missing:
            all_models[model_name] = fields_tuple + tuple(missing)
        res["models"] = frozendict(all_models)
        return res

    @api.model
    def _bks_patch_restart_validation_confirm(self, res):
        doc = etree.XML(res["arch"])
        confirm = self.env._(_BKS_RESTART_VALIDATION_CONFIRM)
        for button in doc.xpath("//button[@name='restart_validation']"):
            button.set("confirm", confirm)
        if not doc.xpath("//button[@name='restart_validation']"):
            return res
        patched = dict(res)
        patched["arch"] = etree.tostring(doc, encoding="unicode")
        return patched

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == "form":
            res = self._bks_patch_restart_validation_confirm(res)
            if self._name in _BKS_TIER_FORM_MODELS:
                res = self._bks_patch_tier_form_arch(self._name, res)
        return res
