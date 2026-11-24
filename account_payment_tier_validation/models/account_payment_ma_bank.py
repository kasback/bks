# Copyright 2025 Spearhead - Ricardo Jara
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.rmg_l10n_ma_account.models.account_payment_method import (
    DGI_PAYMENT_CODES,
)

# RMG compta : virement bancaire (mode journal + canal DGI)
_BKS_MA_TRANSFER_METHOD_CODE = "ma_transfer"
_BKS_MA_TRANSFER_DGI_CODE = "4"
# Canal interne : pas un code DGI. La déclaration fiscale le ramène au virement (4).
_BKS_FOREIGN_TRANSFER_METHOD_CODE = "ma_foreign_transfer"
_BKS_FOREIGN_TRANSFER_DGI_CODE = "8"
_BKS_FOREIGN_TRANSFER_LABEL = "Virement à l'étranger"
_BKS_DGI_TO_MA_METHOD = {dgi: ma for ma, dgi in DGI_PAYMENT_CODES.items()}
_BKS_DGI_TO_MA_METHOD[_BKS_FOREIGN_TRANSFER_DGI_CODE] = (
    _BKS_FOREIGN_TRANSFER_METHOD_CODE
)


def _bks_sync_payment_method_line_from_dgi(records):
    for record in records:
        dgi_code = record.l10n_ma_reports_payment_method
        if not dgi_code:
            continue
        ma_code = _BKS_DGI_TO_MA_METHOD.get(dgi_code)
        if not ma_code:
            continue
        available = record.available_payment_method_line_ids
        line = available.filtered(lambda ln, c=ma_code: ln.code == c)[:1]
        if line:
            record.payment_method_line_id = line


class AccountPayment(models.Model):
    _inherit = "account.payment"

    l10n_ma_reports_payment_method = fields.Selection(
        selection_add=[
            (_BKS_FOREIGN_TRANSFER_DGI_CODE, _BKS_FOREIGN_TRANSFER_LABEL),
        ],
        ondelete={_BKS_FOREIGN_TRANSFER_DGI_CODE: "set null"},
    )

    @api.model
    def _get_method_codes_using_bank_account(self):
        codes = list(super()._get_method_codes_using_bank_account())
        for code in (_BKS_MA_TRANSFER_METHOD_CODE, _BKS_FOREIGN_TRANSFER_METHOD_CODE):
            if code not in codes:
                codes.append(code)
        return codes

    @api.model
    def _get_method_codes_needing_bank_account(self):
        codes = list(super()._get_method_codes_needing_bank_account())
        for code in (_BKS_MA_TRANSFER_METHOD_CODE, _BKS_FOREIGN_TRANSFER_METHOD_CODE):
            if code not in codes:
                codes.append(code)
        return codes

    def _bks_is_foreign_transfer(self):
        self.ensure_one()
        if self.l10n_ma_reports_payment_method == _BKS_FOREIGN_TRANSFER_DGI_CODE:
            return True
        return self.payment_method_code == _BKS_FOREIGN_TRANSFER_METHOD_CODE

    def _bks_is_ma_bank_transfer(self):
        self.ensure_one()
        if self._bks_is_foreign_transfer():
            return False
        if self.payment_method_code == _BKS_MA_TRANSFER_METHOD_CODE:
            return True
        return self.l10n_ma_reports_payment_method == _BKS_MA_TRANSFER_DGI_CODE

    def _bks_ma_transfer_requires_partner_bank(self):
        return self._bks_is_ma_bank_transfer() or self._bks_is_foreign_transfer()

    @api.depends("payment_method_line_id")
    def _compute_l10n_ma_reports_payment_method(self):
        """Garde « Virement à l'étranger » : le compte technique reste un virement."""
        foreign = self.filtered(
            lambda payment: payment.l10n_ma_reports_payment_method
            == _BKS_FOREIGN_TRANSFER_DGI_CODE
            and (
                not payment.payment_method_line_id
                or payment.payment_method_line_id.code
                in (False, _BKS_FOREIGN_TRANSFER_METHOD_CODE)
            )
        )
        super(AccountPayment, self - foreign)._compute_l10n_ma_reports_payment_method()

    def _bks_sync_payment_method_line_from_dgi(self):
        _bks_sync_payment_method_line_from_dgi(self)

    @api.depends(
        "payment_method_code",
        "l10n_ma_reports_payment_method",
        "journal_id.type",
        "state",
    )
    def _compute_show_require_partner_bank(self):
        super()._compute_show_require_partner_bank()
        for payment in self:
            if not payment._bks_ma_transfer_requires_partner_bank():
                continue
            if payment.journal_id.type != "cash":
                payment.show_partner_bank_account = True
            payment.require_partner_bank_account = payment.state == "draft"

    @api.constrains(
        "partner_bank_id",
        "payment_method_line_id",
        "l10n_ma_reports_payment_method",
    )
    def _bks_check_ma_transfer_partner_bank(self):
        for payment in self:
            if not payment._bks_ma_transfer_requires_partner_bank():
                continue
            if payment.partner_bank_id:
                continue
            raise ValidationError(
                _(
                    "Le compte bancaire du partenaire est obligatoire "
                    "lorsque le moyen de paiement est un virement bancaire."
                )
            )

    @api.onchange("l10n_ma_reports_payment_method", "journal_id")
    def _bks_onchange_l10n_ma_sync_payment_method(self):
        self._bks_sync_payment_method_line_from_dgi()


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    l10n_ma_reports_payment_method = fields.Selection(
        selection_add=[
            (_BKS_FOREIGN_TRANSFER_DGI_CODE, _BKS_FOREIGN_TRANSFER_LABEL),
        ],
        ondelete={_BKS_FOREIGN_TRANSFER_DGI_CODE: "set null"},
    )

    def _bks_is_foreign_transfer(self):
        self.ensure_one()
        if self.l10n_ma_reports_payment_method == _BKS_FOREIGN_TRANSFER_DGI_CODE:
            return True
        code = self.payment_method_line_id.code if self.payment_method_line_id else False
        return code == _BKS_FOREIGN_TRANSFER_METHOD_CODE

    def _bks_ma_transfer_requires_partner_bank(self):
        self.ensure_one()
        if self._bks_is_foreign_transfer():
            return True
        code = self.payment_method_line_id.code if self.payment_method_line_id else False
        if code == _BKS_MA_TRANSFER_METHOD_CODE:
            return True
        return self.l10n_ma_reports_payment_method == _BKS_MA_TRANSFER_DGI_CODE

    @api.depends("payment_method_line_id")
    def _compute_l10n_ma_reports_payment_method(self):
        foreign = self.filtered(
            lambda wizard: wizard.l10n_ma_reports_payment_method
            == _BKS_FOREIGN_TRANSFER_DGI_CODE
            and (
                not wizard.payment_method_line_id
                or wizard.payment_method_line_id.code
                in (False, _BKS_FOREIGN_TRANSFER_METHOD_CODE)
            )
        )
        super(
            AccountPaymentRegister, self - foreign
        )._compute_l10n_ma_reports_payment_method()

    def _bks_sync_payment_method_line_from_dgi(self):
        _bks_sync_payment_method_line_from_dgi(self)

    @api.depends(
        "payment_method_line_id",
        "l10n_ma_reports_payment_method",
        "journal_id.type",
    )
    def _compute_show_require_partner_bank(self):
        super()._compute_show_require_partner_bank()
        for wizard in self:
            if not wizard._bks_ma_transfer_requires_partner_bank():
                continue
            if wizard.journal_id.type != "cash":
                wizard.show_partner_bank_account = True
            wizard.require_partner_bank_account = True

    @api.onchange("l10n_ma_reports_payment_method", "journal_id")
    def _bks_onchange_l10n_ma_sync_payment_method(self):
        self._bks_sync_payment_method_line_from_dgi()


class AccountPaymentMethod(models.Model):
    _inherit = "account.payment.method"

    @api.model
    def _get_payment_method_information(self):
        res = super()._get_payment_method_information()
        res[_BKS_FOREIGN_TRANSFER_METHOD_CODE] = {
            "mode": "multi",
            "type": ("bank",),
            "country_id": self.env.ref("base.ma").id,
        }
        return res

    @api.model
    def _bks_setup_foreign_transfer_lines(self):
        """Reprend le compte en suspens du virement local sur la nouvelle ligne."""
        lines = self.env["account.payment.method.line"].search(
            [("code", "=", _BKS_FOREIGN_TRANSFER_METHOD_CODE)]
        )
        for line in lines.filtered(lambda item: not item.payment_account_id):
            journal = line.journal_id
            pool = (
                journal.outbound_payment_method_line_ids
                if line.payment_type == "outbound"
                else journal.inbound_payment_method_line_ids
            )
            sibling = pool.filtered(
                lambda item: item.code == _BKS_MA_TRANSFER_METHOD_CODE
            )[:1]
            if sibling.payment_account_id:
                line.payment_account_id = sibling.payment_account_id


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _bks_with_foreign_transfer_method(self, methods, payment_type):
        if not self._is_payment_method_available(_BKS_FOREIGN_TRANSFER_METHOD_CODE):
            return methods
        foreign = self.env["account.payment.method"].search(
            [
                ("code", "=", _BKS_FOREIGN_TRANSFER_METHOD_CODE),
                ("payment_type", "=", payment_type),
            ],
            limit=1,
        )
        return methods | foreign if foreign else methods

    def _default_inbound_payment_methods(self):
        return self._bks_with_foreign_transfer_method(
            super()._default_inbound_payment_methods(), "inbound"
        )

    def _default_outbound_payment_methods(self):
        return self._bks_with_foreign_transfer_method(
            super()._default_outbound_payment_methods(), "outbound"
        )
