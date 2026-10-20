# Copyright 2025 Spearhead - Ricardo Jara
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, models
from odoo.exceptions import ValidationError

from odoo.addons.rmg_l10n_ma_account.models.account_payment_method import (
    DGI_PAYMENT_CODES,
)

# RMG compta : virement bancaire (mode journal + canal DGI)
_BKS_MA_TRANSFER_METHOD_CODE = "ma_transfer"
_BKS_MA_TRANSFER_DGI_CODE = "4"
_BKS_DGI_TO_MA_METHOD = {dgi: ma for ma, dgi in DGI_PAYMENT_CODES.items()}


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

    @api.model
    def _get_method_codes_using_bank_account(self):
        codes = list(super()._get_method_codes_using_bank_account())
        if _BKS_MA_TRANSFER_METHOD_CODE not in codes:
            codes.append(_BKS_MA_TRANSFER_METHOD_CODE)
        return codes

    @api.model
    def _get_method_codes_needing_bank_account(self):
        codes = list(super()._get_method_codes_needing_bank_account())
        if _BKS_MA_TRANSFER_METHOD_CODE not in codes:
            codes.append(_BKS_MA_TRANSFER_METHOD_CODE)
        return codes

    def _bks_ma_transfer_requires_partner_bank(self):
        self.ensure_one()
        if self.payment_method_code == _BKS_MA_TRANSFER_METHOD_CODE:
            return True
        return self.l10n_ma_reports_payment_method == _BKS_MA_TRANSFER_DGI_CODE

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

    def _bks_ma_transfer_requires_partner_bank(self):
        self.ensure_one()
        code = self.payment_method_line_id.code if self.payment_method_line_id else False
        if code == _BKS_MA_TRANSFER_METHOD_CODE:
            return True
        return self.l10n_ma_reports_payment_method == _BKS_MA_TRANSFER_DGI_CODE

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
