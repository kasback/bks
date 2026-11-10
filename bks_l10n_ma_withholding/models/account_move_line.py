from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_computed_taxes(self):
        """Proposition initiale : TVA de l'article et RAS du moteur.

        Le choix fait ensuite dans la colonne Taxes n'est pas réécrit.
        """
        taxes = super()._get_computed_taxes()
        if self.display_type != "product" or not self.move_id.is_invoice():
            return taxes
        regular = taxes.filtered(lambda tax: not tax.is_withholding_tax_on_payment)
        return regular | self._rmg_applicable_withholding_taxes(regular)

    def _rmg_apply_withholding_proposal(self):
        """La RAS reste une proposition, pas un verrou sur la colonne Taxes."""
        return

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.filtered("purchase_line_id")._bks_add_withholding_proposal()
        return lines

    def _bks_add_withholding_proposal(self):
        """Lignes reprises d'un bon de commande : elles arrivent avec la TVA seule."""
        for line in self:
            if (
                line.display_type != "product"
                or not line.move_id.is_invoice()
                or line.move_id.state != "draft"
                or line.tax_ids.filtered("is_withholding_tax_on_payment")
            ):
                continue
            proposal = line._rmg_applicable_withholding_taxes(line.tax_ids)
            if proposal:
                line.tax_ids |= proposal
