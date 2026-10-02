# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo import api, models


class PurchaseRequestLine(models.Model):
    _inherit = "purchase.request.line"

    # Champs mis à jour par le module purchase_request (allocations, PO, stock).
    _BKS_FULFILLMENT_WRITABLE = frozenset(
        {
            "qty_in_progress",
            "qty_done",
            "qty_cancelled",
            "qty_to_buy",
            "pending_qty_to_receive",
            "purchase_state",
            "cancelled",
            "product_uom_id",
        }
    )

    @api.depends(
        "purchase_lines",
        "request_id.state",
        "request_id.validation_status",
    )
    def _compute_is_editable(self):
        super()._compute_is_editable()
        locked_statuses = self.env["purchase.request"]._BKS_LOCK_VALIDATION_STATUSES
        for line in self:
            if line.request_id.validation_status in locked_statuses:
                line.is_editable = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            request = self.env["purchase.request"].browse(vals.get("request_id"))
            if request.exists() and not request.is_editable:
                raise UserError(
                    self.env._(
                        "Impossible d'ajouter une ligne : la demande d'achat "
                        "est verrouillée (validation en cours ou terminée)."
                    )
                )
        return super().create(vals_list)

    def _bks_get_locked_line_write_violations(self, vals):
        """Champs interdits qui changeraient réellement la ligne verrouillée."""
        self.ensure_one()
        violations = []
        for key, new_val in vals.items():
            if key in self._BKS_FULFILLMENT_WRITABLE:
                continue
            field = self._fields.get(key)
            if not field:
                violations.append(key)
                continue
            if field.type == "many2one":
                new_id = new_val or False
                old_id = self[key].id if self[key] else False
                if new_id != old_id:
                    violations.append(key)
            elif field.type in ("one2many", "many2many"):
                violations.append(key)
            elif new_val != self[key]:
                violations.append(key)
        return violations

    def write(self, vals):
        if vals:
            for line in self:
                if not line.is_editable and line._bks_get_locked_line_write_violations(
                    vals
                ):
                    raise UserError(
                        self.env._(
                            "Impossible de modifier la ligne « %(name)s » : "
                            "la demande d'achat est verrouillée.",
                            name=line.display_name,
                        )
                    )
        return super().write(vals)

    def unlink(self):
        for line in self:
            if not line.is_editable:
                raise UserError(
                    self.env._(
                        "Impossible de supprimer la ligne « %(name)s » : "
                        "la demande d'achat est verrouillée.",
                        name=line.display_name,
                    )
                )
        return super().unlink()

    def action_show_details(self):
        for line in self:
            if not line.is_editable:
                raise UserError(
                    self.env._(
                        "Le détail de la ligne n'est pas modifiable pendant "
                        "ou après le circuit de validation."
                    )
                )
        return super().action_show_details()
