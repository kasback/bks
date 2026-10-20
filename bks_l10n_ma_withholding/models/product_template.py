from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    bks_withholding_nature = fields.Selection(
        [
            ("service", "Prestation de services"),
            ("equipment", "Bien d'équipement"),
            ("works", "Travaux"),
            ("none", "Non concernée"),
        ],
        string="Retenue à la source",
        required=True,
        default="service",
    )

    @api.depends("bks_withholding_nature")
    def _compute_rmg_withholding_category(self):
        for product in self:
            nature = product.bks_withholding_nature
            product.rmg_withholding_category = False if nature == "none" else nature

    def _auto_init(self):
        cr = self.env.cr
        cr.execute(
            """
            SELECT 1 FROM information_schema.columns
             WHERE table_name = 'product_template'
               AND column_name = 'bks_withholding_nature'
            """
        )
        missing = not cr.fetchone()
        super()._auto_init()
        if not missing:
            return
        cr.execute(
            """
            UPDATE product_template
               SET bks_withholding_nature = CASE
                    WHEN type = 'service'
                        THEN COALESCE(rmg_withholding_service_nature, 'service')
                    WHEN type = 'consu'
                        THEN COALESCE(rmg_withholding_goods_nature, 'equipment')
                    ELSE 'none'
               END
            """
        )
