from odoo import models


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
