import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    genex_exported = fields.Boolean(
        string="Exporté GENEX",
        copy=False,
        readonly=True,
        index=True,
        help="Écriture déjà transmise à iMal via l'export GENEX.",
    )
    genex_export_date = fields.Datetime(
        string="Date export GENEX",
        copy=False,
        readonly=True,
    )
    genex_export_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Export GENEX par",
        copy=False,
        readonly=True,
    )

    @api.depends("genex_exported")
    def _compute_show_reset_to_draft_button(self):
        super()._compute_show_reset_to_draft_button()
        for move in self.filtered("genex_exported"):
            move.show_reset_to_draft_button = False

    def button_draft(self):
        exported = self.filtered("genex_exported")
        if exported:
            names = ", ".join(exported.mapped("name")[:10])
            raise UserError(
                _(
                    "Impossible de remettre en brouillon une écriture déjà "
                    "exportée vers GENEX :\n%(names)s",
                    names=names,
                )
            )
        return super().button_draft()

    @staticmethod
    def _genex_rib_from_bank(bank):
        if not bank:
            return None
        raw = bank.sanitized_acc_number or bank.acc_number or ""
        rib = re.sub(r"[\s\-]", "", str(raw))
        return rib[:24] if rib else None

    def _get_genex_related_payment(self):
        self.ensure_one()
        if self.origin_payment_id:
            return self.origin_payment_id
        payment = self.env["account.payment"].search(
            [("move_id", "=", self.id)], limit=1
        )
        if payment:
            return payment
        for payments in (self.reconciled_payment_ids, self.matched_payment_ids):
            if payments:
                return payments[0]
        return self.env["account.payment"]

    def _get_genex_rib(self):
        """RIB GENEX (24 car.) : paiement, écriture ou partenaire."""
        self.ensure_one()
        partner = self.partner_id
        if partner and partner.genex_rib:
            return str(partner.genex_rib).strip()[:24] or None

        rib = self._genex_rib_from_bank(self.partner_bank_id)
        if rib:
            return rib

        payment = self._get_genex_related_payment()
        rib = self._genex_rib_from_bank(payment.partner_bank_id)
        if rib:
            return rib

        if partner:
            return self._genex_rib_from_bank(partner.bank_ids[:1])
        return None

    @api.model
    def _get_validation_exceptions(self, extra_domain=None, add_base_exceptions=True):
        """Autoriser le marquage GENEX après validation tier des écritures."""
        res = super()._get_validation_exceptions(extra_domain, add_base_exceptions)
        return res + [
            "genex_exported",
            "genex_export_date",
            "genex_export_user_id",
        ]

    def _mark_genex_exported(self):
        self.write(
            {
                "genex_exported": True,
                "genex_export_date": fields.Datetime.now(),
                "genex_export_user_id": self.env.user.id,
            }
        )

    def _bks_genex_fnp_record(self):
        """FNP liée à cette écriture (provision ou extourne), si module achats installé."""
        self.ensure_one()
        if "bks.purchase.fnp" not in self.env:
            return self.env["bks.purchase.fnp"]
        Fnp = self.env["bks.purchase.fnp"]
        fnp = Fnp.search([("move_id", "=", self.id)], limit=1)
        if not fnp:
            fnp = Fnp.search([("reversal_move_id", "=", self.id)], limit=1)
        return fnp

    def _bks_genex_reception_reference(self):
        """Référence réception pour FNP / extourne (colonne JV_REF GENEX)."""
        self.ensure_one()
        fnp = self._bks_genex_fnp_record()
        if fnp and fnp.picking_id:
            return (fnp.picking_id.name or "").strip()
        return ""

    def _bks_genex_incoming_picking(self):
        """Réception stock liée à l'écriture (module stock_account)."""
        self.ensure_one()
        stock_moves = getattr(self, "stock_move_ids", None)
        if not stock_moves:
            return self.env["stock.picking"]
        pickings = stock_moves.mapped("picking_id").filtered(
            lambda p: p.picking_type_code == "incoming"
        )
        return pickings[:1]

    def _bks_genex_reconciliation_reference(self):
        """Référence de lettrage export GENEX (dernière colonne ODOO_GENEX)."""
        self.ensure_one()
        fnp = self._bks_genex_fnp_record()
        if fnp and fnp.picking_id:
            return (fnp.picking_id.name or "").strip()
        if self.move_type in ("in_invoice", "in_refund", "in_receipt"):
            return (self.name or self.ref or "").strip()
        payment = self._get_genex_related_payment()
        if payment and (
            self.origin_payment_id
            or payment.move_id == self
        ):
            return (payment.name or payment.payment_reference or "").strip()
        picking = self._bks_genex_incoming_picking()
        if picking:
            return (picking.name or "").strip()
        return ""
