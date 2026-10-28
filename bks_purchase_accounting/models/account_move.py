from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import frozendict


class AccountMove(models.Model):
    _inherit = "account.move"

    bks_fnp_reversal_move_id = fields.Many2one(
        "account.move",
        string="Extourne FNP",
        copy=False,
        readonly=True,
    )
    bks_guarantee_amount = fields.Monetary(
        string="Retenue de garantie TTC",
        currency_field="currency_id",
        tracking=True,
        help="Montant TTC crédité sur le compte de retenue de garantie "
        "paramétré sur la société. Le net à payer reste sur le compte fournisseur.",
    )
    bks_guarantee_needed = fields.Binary(
        compute="_compute_bks_guarantee_needed",
        exportable=False,
    )
    bks_guarantee_dirty = fields.Boolean(compute="_compute_bks_guarantee_needed")
    bks_guarantee_payment_ids = fields.One2many(
        "account.payment",
        "bks_guarantee_move_id",
        string="Règlements de la retenue de garantie",
        copy=False,
    )
    bks_guarantee_payment_count = fields.Integer(
        compute="_compute_bks_guarantee_payment_count",
    )
    bks_guarantee_to_pay = fields.Boolean(compute="_compute_bks_guarantee_to_pay")

    def _bks_guarantee_account(self):
        """Compte unique paramétré sur la société.

        Une facture déjà comptabilisée garde le compte de sa ligne,
        pour que le règlement et le lettrage restent sur ce compte.
        """
        self.ensure_one()
        if self.state == "posted":
            line = self.line_ids.filtered(
                lambda line: line.display_type == "bks_guarantee" and line.account_id
            )[:1]
            if line:
                return line.account_id
        return self.company_id.bks_guarantee_account_id

    @api.constrains("bks_guarantee_amount", "amount_total", "move_type", "currency_id")
    def _check_bks_guarantee_amount(self):
        for move in self:
            move._bks_check_guarantee_amount()

    def _bks_check_guarantee_amount(self):
        self.ensure_one()
        if self.env.context.get("bks_skip_guarantee_check"):
            return
        if self.move_type != "in_invoice" or not self.bks_guarantee_amount:
            return
        currency = self.currency_id
        if currency.compare_amounts(self.bks_guarantee_amount, 0.0) < 0:
            raise ValidationError("La retenue de garantie ne peut pas être négative.")
        if not self.invoice_line_ids:
            return
        total = self.with_context(bks_skip_guarantee_check=True).amount_total
        if currency.is_zero(total):
            return
        if currency.compare_amounts(self.bks_guarantee_amount, total) > 0:
            raise ValidationError(
                "La retenue de garantie ne peut pas dépasser le TTC de la facture."
            )

    @api.depends(
        "invoice_payment_term_id",
        "invoice_date",
        "currency_id",
        "amount_total_in_currency_signed",
        "invoice_date_due",
        "bks_guarantee_amount",
        "partner_id",
        "commercial_partner_id",
        "company_id",
    )
    def _compute_needed_terms(self):
        super()._compute_needed_terms()
        for invoice in self:
            invoice._bks_apply_guarantee_on_terms()

    def _bks_apply_guarantee_on_terms(self):
        """Retire la garantie du crédit 367104. Le TTC de la garantie part sur le 369100."""
        self.ensure_one()
        if self.move_type != "in_invoice" or not self.needed_terms:
            return
        if not self._bks_guarantee_account():
            return
        currency = self.currency_id
        company_currency = self.company_currency_id
        guarantee_currency = currency.round(self.bks_guarantee_amount or 0.0)
        if currency.is_zero(guarantee_currency):
            return
        date = self.invoice_date or self.date or fields.Date.context_today(self)
        guarantee_balance = company_currency.round(
            currency._convert(
                guarantee_currency, company_currency, self.company_id, date
            )
        )
        remaining_currency = guarantee_currency
        remaining_balance = guarantee_balance
        keys = sorted(
            self.needed_terms,
            key=lambda key: key.get("date_maturity") or date,
        )
        new_terms = {}
        for key in keys:
            values = dict(self.needed_terms[key])
            balance = values.get("balance") or 0.0
            amount_currency = values.get("amount_currency") or 0.0
            if balance < 0 and not company_currency.is_zero(remaining_balance):
                take_balance = company_currency.round(
                    min(remaining_balance, abs(balance))
                )
                values["balance"] = company_currency.round(balance + take_balance)
                remaining_balance = company_currency.round(
                    remaining_balance - take_balance
                )
            if amount_currency < 0 and not currency.is_zero(remaining_currency):
                take_currency = currency.round(
                    min(remaining_currency, abs(amount_currency))
                )
                values["amount_currency"] = currency.round(
                    amount_currency + take_currency
                )
                remaining_currency = currency.round(remaining_currency - take_currency)
            new_terms[key] = values
        if not currency.is_zero(remaining_currency) or not company_currency.is_zero(
            remaining_balance
        ):
            values = new_terms[keys[-1]]
            values["balance"] = company_currency.round(
                (values.get("balance") or 0.0) + remaining_balance
            )
            values["amount_currency"] = currency.round(
                (values.get("amount_currency") or 0.0) + remaining_currency
            )
        self.needed_terms = new_terms

    @api.depends(
        "bks_guarantee_amount",
        "move_type",
        "state",
        "currency_id",
        "company_id",
        "company_currency_id",
        "partner_id",
        "commercial_partner_id",
        "invoice_date",
        "date",
        "invoice_date_due",
        "invoice_line_ids",
    )
    def _compute_bks_guarantee_needed(self):
        for move in self:
            move.bks_guarantee_dirty = True
            move.bks_guarantee_needed = {}
            if move.state == "cancel" or move.move_type != "in_invoice":
                continue
            if not move.invoice_line_ids:
                continue
            currency = move.currency_id
            amount = currency.round(move.bks_guarantee_amount or 0.0)
            if currency.is_zero(amount):
                continue
            account = move._bks_guarantee_account()
            if not account:
                continue
            company_currency = move.company_currency_id
            date = move.invoice_date or move.date or fields.Date.context_today(move)
            balance = company_currency.round(
                currency._convert(amount, company_currency, move.company_id, date)
            )
            key = frozendict(
                {
                    "move_id": move.id,
                    "bks_is_guarantee_line": True,
                }
            )
            move.bks_guarantee_needed = {
                key: {
                    "name": move._bks_guarantee_line_label(),
                    "account_id": account.id,
                    "partner_id": move.commercial_partner_id.id,
                    "currency_id": currency.id,
                    "balance": -balance,
                    "amount_currency": -amount,
                    "date_maturity": move.invoice_date_due or date,
                    "sequence": 110,
                }
            }

    def _bks_guarantee_line_label(self):
        self.ensure_one()
        label = "Retenue de garantie"
        ref = self.ref or (self.name if self.name and self.name != "/" else "")
        if ref:
            return "%s %s" % (label, ref)
        return label

    def _get_sync_stack(self, container):
        stack, update_containers = super()._get_sync_stack(container)
        _tax_container, invoice_container, _misc_container = update_containers()
        stack.append(
            (
                15,
                self._sync_dynamic_line(
                    existing_key_fname="bks_guarantee_key",
                    needed_vals_fname="bks_guarantee_needed",
                    needed_dirty_fname="bks_guarantee_dirty",
                    line_type="bks_guarantee",
                    container=invoice_container,
                ),
            )
        )
        return stack, update_containers

    def _bks_open_guarantee_payments(self):
        return self.bks_guarantee_payment_ids.filtered(
            lambda payment: payment.state not in ("canceled", "rejected")
        )

    @api.depends("bks_guarantee_payment_ids.state")
    def _compute_bks_guarantee_payment_count(self):
        for move in self:
            move.bks_guarantee_payment_count = len(move._bks_open_guarantee_payments())

    @api.depends(
        "state",
        "move_type",
        "bks_guarantee_amount",
        "currency_id",
        "bks_guarantee_payment_ids.state",
    )
    def _compute_bks_guarantee_to_pay(self):
        for move in self:
            amount = move.bks_guarantee_amount or 0.0
            open_payment = move._bks_open_guarantee_payments()
            move.bks_guarantee_to_pay = (
                move.move_type == "in_invoice"
                and move.state == "posted"
                and not move.currency_id.is_zero(amount)
                and not open_payment
            )

    def action_bks_pay_guarantee(self):
        """Règlement de la garantie : débit 369100, crédit du journal, puis lettrage."""
        self.ensure_one()
        if self.move_type != "in_invoice" or self.state != "posted":
            raise UserError(
                "La retenue de garantie se règle sur une facture fournisseur comptabilisée."
            )
        if self.currency_id.is_zero(self.bks_guarantee_amount or 0.0):
            raise UserError("Renseignez le montant de la retenue de garantie.")
        if self._bks_open_guarantee_payments():
            raise UserError(
                "Un règlement de la retenue de garantie existe déjà pour cette facture."
            )
        lines = self.line_ids.filtered(
            lambda line: line.display_type == "bks_guarantee" and not line.reconciled
        )
        if not lines or self.currency_id.is_zero(
            sum(abs(line.amount_residual_currency) for line in lines)
        ):
            raise UserError("Aucune retenue de garantie ouverte sur cette facture.")
        journal = self.env["account.journal"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("type", "=", "bank"),
            ],
            limit=1,
        )
        if not journal:
            raise UserError("Aucun journal de banque n'est défini pour cette société.")
        amount = sum(abs(line.amount_residual_currency) for line in lines)
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.commercial_partner_id.id,
                "amount": amount,
                "currency_id": self.currency_id.id,
                "journal_id": journal.id,
                "date": fields.Date.context_today(self),
                "memo": self._bks_guarantee_line_label(),
                "bks_guarantee_move_id": self.id,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Régler la garantie",
            "res_model": "account.payment",
            "view_mode": "form",
            "res_id": payment.id,
            "target": "current",
        }

    def action_open_bks_guarantee_payments(self):
        self.ensure_one()
        payments = self._bks_open_guarantee_payments()
        return payments._get_records_action(name="Retenue de garantie")

    def action_post(self):
        for move in self:
            move._bks_check_guarantee_amount()
            if move.move_type == "in_invoice" and move.bks_guarantee_amount:
                total = move.with_context(bks_skip_guarantee_check=True).amount_total
                if move.currency_id.compare_amounts(move.bks_guarantee_amount, total) > 0:
                    raise UserError(
                        "La retenue de garantie ne peut pas dépasser le TTC de la facture."
                    )
                if not move._bks_guarantee_account():
                    raise UserError(
                        "Renseignez le compte de retenue de garantie "
                        "dans les paramètres de comptabilité."
                    )
        return super().action_post()

    def _post(self, soft=True):
        invoices = self.filtered(
            lambda move: move.is_purchase_document(include_receipts=True)
            and move.state == "draft"
            and not move.bks_fnp_reversal_move_id
        )
        for invoice in invoices:
            reversal = self.env["bks.purchase.fnp"]._reverse_for_invoice(invoice)
            if reversal:
                invoice.bks_fnp_reversal_move_id = reversal.id
        posted = super()._post(soft)
        posted._bks_reconcile_guarantee_from_payment()
        return posted

    def _bks_reconcile_guarantee_from_payment(self):
        for move in self:
            payment = move.origin_payment_id
            invoice = payment.bks_guarantee_move_id
            if not invoice:
                continue
            account = invoice._bks_guarantee_account()
            if not account:
                continue
            invoice_lines = invoice.line_ids.filtered(
                lambda line: line.display_type == "bks_guarantee"
                and line.account_id == account
                and not line.reconciled
            )
            payment_lines = move.line_ids.filtered(
                lambda line: line.account_id == account and not line.reconciled
            )
            if invoice_lines and payment_lines:
                (invoice_lines + payment_lines).reconcile()


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    display_type = fields.Selection(
        selection_add=[("bks_guarantee", "Retenue de garantie")],
        ondelete={"bks_guarantee": "cascade"},
    )
    bks_is_guarantee_line = fields.Boolean(string="Ligne de retenue de garantie")
    bks_guarantee_key = fields.Binary(
        compute="_compute_bks_guarantee_key",
        exportable=False,
    )

    @api.depends("display_type", "move_id", "bks_is_guarantee_line")
    def _compute_bks_guarantee_key(self):
        for line in self:
            if line.display_type == "bks_guarantee" or line.bks_is_guarantee_line:
                line.bks_guarantee_key = frozendict(
                    {
                        "move_id": line.move_id.id,
                        "bks_is_guarantee_line": True,
                    }
                )
            else:
                line.bks_guarantee_key = False

    @api.depends(
        "product_id",
        "move_id.ref",
        "move_id.payment_reference",
        "display_type",
        "move_id.name",
    )
    def _compute_name(self):
        guarantee_lines = self.filtered(lambda line: line.display_type == "bks_guarantee")
        for line in guarantee_lines:
            line.name = line.move_id._bks_guarantee_line_label()
        super(AccountMoveLine, self - guarantee_lines)._compute_name()
