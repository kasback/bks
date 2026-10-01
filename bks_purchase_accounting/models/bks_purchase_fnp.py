from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class BksPurchaseFnp(models.Model):
    _name = "bks.purchase.fnp"
    _description = "Provision FNP achat"
    _order = "id"

    name = fields.Char(required=True, copy=False, readonly=True, default="/")
    company_id = fields.Many2one("res.company", required=True, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    partner_id = fields.Many2one("res.partner", string="Fournisseur", readonly=True)
    purchase_order_id = fields.Many2one("purchase.order", readonly=True, index=True)
    purchase_line_id = fields.Many2one("purchase.order.line", readonly=True, index=True)
    picking_id = fields.Many2one("stock.picking", readonly=True, index=True)
    stock_move_id = fields.Many2one("stock.move", readonly=True)
    product_id = fields.Many2one("product.product", readonly=True)
    expense_account_id = fields.Many2one("account.account", readonly=True)
    quantity = fields.Float(
        string="Quantité (UdM commande)",
        digits="Product Unit",
        readonly=True,
    )
    amount = fields.Monetary(currency_field="currency_id", readonly=True)
    qty_reversed = fields.Float(
        string="Quantité extournée",
        digits="Product Unit",
        readonly=True,
    )
    amount_reversed = fields.Monetary(
        string="Montant extourné",
        currency_field="currency_id",
        readonly=True,
    )
    move_id = fields.Many2one("account.move", string="Écriture FNP", readonly=True)
    reversal_move_id = fields.Many2one("account.move", string="Écriture d'extourne", readonly=True)
    invoice_id = fields.Many2one("account.move", string="Facture fournisseur", readonly=True)
    state = fields.Selection(
        [
            ("open", "Ouverte"),
            ("partial", "Partiellement extournée"),
            ("reversed", "Extournée"),
            ("cancel", "Annulée"),
        ],
        default="open",
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("bks.purchase.fnp") or "/"
        return super().create(vals_list)

    def _remaining_qty(self):
        self.ensure_one()
        return self.quantity - self.qty_reversed

    def _remaining_amount(self):
        self.ensure_one()
        if float_is_zero(self.quantity, precision_digits=6):
            return self.amount - self.amount_reversed
        ratio = self._remaining_qty() / self.quantity
        return self.currency_id.round(self.amount * ratio)

    @api.model
    def _get_fnp_accounts(self, company):
        account = company.bks_fnp_account_id
        journal = company.bks_fnp_journal_id
        if not account or not journal:
            raise UserError(
                _(
                    "Configurez le compte FNP et le journal FNP achats "
                    "(Comptabilité → Configuration → Paramètres → Achats)."
                )
            )
        return journal, account

    @api.model
    def _get_expense_account(self, po_line):
        product = po_line.product_id
        if not product:
            raise UserError(_("La ligne de commande %s n'a pas de produit.") % po_line.display_name)
        accounts = product.product_tmpl_id.get_product_accounts(
            fiscal_pos=po_line.order_id.fiscal_position_id
        )
        account = accounts.get("expense")
        if not account:
            raise UserError(
                _("Compte de charge manquant pour le produit %s.") % product.display_name
            )
        return account

    @api.model
    def _line_unit_price_ht(self, po_line):
        return po_line._get_gross_price_unit()

    @api.model
    def _amount_from_qty(self, po_line, qty):
        company = po_line.company_id
        price = self._line_unit_price_ht(po_line)
        amount = po_line.currency_id._convert(
            qty * price,
            company.currency_id,
            company,
            po_line.order_id.date_order or fields.Date.context_today(self),
        )
        return company.currency_id.round(amount)

    @api.model
    def _create_provision_from_picking(self, picking):
        picking.ensure_one()
        company = picking.company_id
        journal, fnp_account = self._get_fnp_accounts(company)

        line_vals = []
        fnp_records = self.env["bks.purchase.fnp"]
        precision = self.env["decimal.precision"].precision_get("Product Unit")

        for move in picking.move_ids.filtered(
            lambda m: m.purchase_line_id and m.state == "done" and not m.origin_returned_move_id
        ):
            po_line = move.purchase_line_id
            if po_line.display_type or getattr(po_line, "is_downpayment", False):
                continue
            qty = move.product_uom._compute_quantity(move.quantity, po_line.product_uom_id)
            if float_is_zero(qty, precision_digits=precision):
                continue
            amount = self._amount_from_qty(po_line, qty)
            if company.currency_id.is_zero(amount):
                continue
            expense_account = self._get_expense_account(po_line)
            fnp = self.create(
                {
                    "company_id": company.id,
                    "partner_id": picking.partner_id.id,
                    "purchase_order_id": po_line.order_id.id,
                    "purchase_line_id": po_line.id,
                    "picking_id": picking.id,
                    "stock_move_id": move.id,
                    "product_id": po_line.product_id.id,
                    "expense_account_id": expense_account.id,
                    "quantity": qty,
                    "amount": amount,
                }
            )
            fnp_records |= fnp
            line_vals.extend(
                fnp._prepare_provision_move_line_vals(amount, expense_account, fnp_account, po_line)
            )

        if not fnp_records:
            return self.env["account.move"]

        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": journal.id,
                "date": picking.date_done.date() if picking.date_done else fields.Date.context_today(self),
                "ref": _("FNP %s — %s") % (picking.name, picking.purchase_id.name),
                "partner_id": picking.partner_id.id,
                "company_id": company.id,
                "line_ids": line_vals,
            }
        )
        move.action_post()
        fnp_records.write({"move_id": move.id})
        picking.message_post(
            body=_("Provision FNP enregistrée : %s") % move._get_html_link(),
        )
        return move

    def _prepare_provision_move_line_vals(self, amount, expense_account, fnp_account, po_line):
        self.ensure_one()
        name = _("FNP %s") % (po_line.product_id.display_name,)
        analytic = po_line.analytic_distribution or False
        return [
            (
                0,
                0,
                {
                    "name": name,
                    "partner_id": po_line.partner_id.id,
                    "account_id": expense_account.id,
                    "debit": amount,
                    "credit": 0.0,
                    "analytic_distribution": analytic,
                    "product_id": po_line.product_id.id,
                },
            ),
            (
                0,
                0,
                {
                    "name": name,
                    "partner_id": po_line.partner_id.id,
                    "account_id": fnp_account.id,
                    "debit": 0.0,
                    "credit": amount,
                    "analytic_distribution": analytic,
                },
            ),
        ]

    @api.model
    def _reverse_for_invoice(self, invoice):
        if invoice.move_type not in ("in_invoice", "in_receipt"):
            return self.env["account.move"]

        company = invoice.company_id
        journal, fnp_account = self._get_fnp_accounts(company)
        line_vals = []
        touched = self.env["bks.purchase.fnp"]
        precision = self.env["decimal.precision"].precision_get("Product Unit")

        for inv_line in invoice.invoice_line_ids.filtered(
            lambda l: l.display_type == "product" and l.purchase_line_id
        ):
            po_line = inv_line.purchase_line_id
            qty_invoice = inv_line.product_uom_id._compute_quantity(
                inv_line.quantity, po_line.product_uom_id
            )
            if float_is_zero(qty_invoice, precision_digits=precision):
                continue

            open_fnps = self.search(
                [
                    ("company_id", "=", company.id),
                    ("purchase_line_id", "=", po_line.id),
                    ("state", "in", ("open", "partial")),
                ],
                order="id",
            )
            qty_left = qty_invoice
            for fnp in open_fnps:
                if float_is_zero(qty_left, precision_digits=precision):
                    break
                reverse_qty = min(fnp._remaining_qty(), qty_left)
                if float_is_zero(reverse_qty, precision_digits=precision):
                    continue
                reverse_amount = fnp.currency_id.round(
                    reverse_qty / fnp.quantity * fnp.amount
                ) if not float_is_zero(fnp.quantity, precision_digits=precision) else fnp._remaining_amount()

                line_vals.extend(
                    fnp._prepare_reversal_move_line_vals(
                        reverse_amount, fnp_account, inv_line.name or fnp.product_id.display_name
                    )
                )
                fnp.qty_reversed += reverse_qty
                fnp.amount_reversed += reverse_amount
                if float_compare(fnp.qty_reversed, fnp.quantity, precision_digits=precision) >= 0:
                    fnp.state = "reversed"
                else:
                    fnp.state = "partial"
                fnp.invoice_id = invoice.id
                touched |= fnp
                qty_left -= reverse_qty

        if not line_vals:
            return self.env["account.move"]

        reversal = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": journal.id,
                "date": invoice.date or fields.Date.context_today(self),
                "ref": _("Extourne FNP — %s") % (invoice.name or invoice.ref or invoice.id),
                "partner_id": invoice.partner_id.id,
                "company_id": company.id,
                "line_ids": line_vals,
            }
        )
        reversal.action_post()
        touched.write({"reversal_move_id": reversal.id})
        invoice.message_post(
            body=_("Extourne FNP : %s") % reversal._get_html_link(),
        )
        return reversal

    def _prepare_reversal_move_line_vals(self, amount, fnp_account, label):
        self.ensure_one()
        name = _("Extourne FNP %s") % label
        analytic = self.purchase_line_id.analytic_distribution or False
        return [
            (
                0,
                0,
                {
                    "name": name,
                    "partner_id": self.partner_id.id,
                    "account_id": fnp_account.id,
                    "debit": amount,
                    "credit": 0.0,
                },
            ),
            (
                0,
                0,
                {
                    "name": name,
                    "partner_id": self.partner_id.id,
                    "account_id": self.expense_account_id.id,
                    "debit": 0.0,
                    "credit": amount,
                    "analytic_distribution": analytic,
                    "product_id": self.product_id.id,
                },
            ),
        ]
