from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    bks_l10n_ma_withholding_on_invoice = fields.Boolean(
        string="RAS à la facture fournisseur (BKS)",
        default=True,
        help="Les retenues à la source achat sont comptabilisées à la validation "
        "de la facture fournisseur ; le règlement paie le montant net sans "
        "réimputer la RAS.",
    )
