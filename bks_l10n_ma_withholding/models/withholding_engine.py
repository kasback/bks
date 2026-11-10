from odoo import api, models


class WithholdingEngine(models.AbstractModel):
    _inherit = "rmg.withholding.engine"

    @api.model
    def _service_vat_withholdings(self, context):
        """Sans seuil de montant : la RAS TVA est connue dès le choix de l'article."""
        context.invoice_threshold = -1.0
        context.monthly_threshold = -1.0
        return super()._service_vat_withholdings(context)
