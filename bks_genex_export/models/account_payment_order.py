import io
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import file_path

try:
    import openpyxl
except ImportError as exc:
    openpyxl = None
    _openpyxl_import_error = exc

_OP_TEMPLATE_PATH = "bks_genex_export/static/src/templates/MODEL_OP.xlsx"


class AccountPayment(models.Model):
    _inherit = "account.payment"

    bks_show_payment_order_button = fields.Boolean(
        compute="_compute_bks_payment_order_button",
    )

    @api.depends(
        "state",
        "validation_status",
        "move_id",
        "bks_tier_governed",
    )
    def _compute_bks_payment_order_button(self):
        for pay in self:
            pay.bks_show_payment_order_button = (
                pay.bks_tier_governed
                and pay.validation_status == "validated"
                and pay.state == "in_process"
                and pay.move_id
            )

    @staticmethod
    def _bks_op_reference_suffix(payment, pay_date):
        base = payment.name or payment.payment_reference or str(payment.id)
        match = re.search(r"(\d+)\s*$", base.replace("/", " "))
        num = (match.group(1) if match else str(payment.id))[-4:].lstrip("0") or "0"
        return "%s/%02d/%02d" % (num, pay_date.month, pay_date.year % 100)

    @staticmethod
    def _bks_sanitize_rib(rib):
        return re.sub(r"[\s\-]", "", str(rib or ""))[:24]

    def _bks_format_rib_spaced(self, rib):
        clean = self._bks_sanitize_rib(rib)
        if len(clean) != 24:
            return clean or "N RIB"
        parts = [
            clean[0:3],
            clean[3:6],
            clean[6:8],
            clean[8:12],
            clean[12:13],
            clean[13:17],
            clean[17:21],
            clean[21:23],
            clean[23:24],
        ]
        return " ".join(parts)

    def _bks_payment_order_label(self):
        self.ensure_one()
        bills = self.reconciled_bill_ids
        if not bills:
            bills = self.invoice_ids.filtered(
                lambda move: move.move_type in ("in_invoice", "in_refund")
            )
        parts = []
        for bill in bills:
            fn = bill.name or "FN"
            designation = (
                bill.ref
                or bill.invoice_origin
                or bill.payment_reference
                or bill.narration
                or ""
            )
            if isinstance(designation, dict):
                designation = ""
            else:
                designation = str(designation or "")[:80]
            parts.append(("%s %s" % (fn, designation)).strip())
        if parts:
            return " / ".join(parts)[:255]
        return self.memo or self.payment_reference or self.name or ""

    def _bks_settlement_mode_label(self):
        self.ensure_one()
        field = self._fields.get("l10n_ma_reports_payment_method")
        code = self.l10n_ma_reports_payment_method
        if field and code:
            labels = dict(field._description_selection(self.env))
            label = labels.get(code)
            if label:
                return label
        if self.payment_method_line_id:
            return self.payment_method_line_id.name or ""
        return ""

    def _bks_check_payment_order_print_eligibility(self):
        self.ensure_one()
        pay = self
        errors = []
        if not pay.bks_tier_governed:
            errors.append(
                _("%(name)s : hors circuit de règlement.", name=pay.display_name)
            )
        if pay.validation_status != "validated":
            errors.append(
                _(
                    "%(name)s : le circuit de validation n'est pas approuvé.",
                    name=pay.display_name,
                )
            )
        if pay.state != "in_process":
            errors.append(
                _(
                    "%(name)s : le paiement doit être en cours de traitement.",
                    name=pay.display_name,
                )
            )
        if not pay.move_id:
            errors.append(
                _(
                    "%(name)s : aucune écriture comptable associée.",
                    name=pay.display_name,
                )
            )
        if errors:
            raise UserError("\n".join(errors))

    def _bks_build_payment_order_workbook(self):
        if not openpyxl:
            raise UserError(
                _("Bibliothèque Python openpyxl requise : %s") % _openpyxl_import_error
            )
        self.ensure_one()
        pay = self
        company = pay.company_id
        pay_date = pay.date or fields.Date.context_today(self)
        wb = openpyxl.load_workbook(file_path(_OP_TEMPLATE_PATH))
        ws = wb.active
        op_ref = self._bks_op_reference_suffix(pay, pay_date)
        rib = pay.partner_bank_id.sanitized_acc_number or pay.partner_bank_id.acc_number
        debit_rib = company.genex_ov_debit_rib_display or ""

        ws["F6"] = pay_date.strftime("%d/%m/%y")
        ws["C9"] = op_ref
        ws["B12"] = pay.partner_id.name or ""
        ws["D12"] = self._bks_payment_order_label()
        ws["F12"] = pay.amount
        ws["F13"] = "=SUM(F12:F12)"

        if pay._bks_is_ma_bank_transfer():
            ws["E17"] = op_ref.split("/")[0] + "/%02d" % (pay_date.year % 100)
        else:
            mode = self._bks_settlement_mode_label() or _("Chèque")
            ws["C16"] = mode

        if debit_rib:
            ws["D19"] = debit_rib
        ws["D20"] = self._bks_format_rib_spaced(rib)

        return wb

    def _bks_payment_order_filename(self):
        self.ensure_one()
        safe_name = re.sub(r"[^\w\-]+", "_", self.name or str(self.id))
        return "Ordre_paiement_%s.xlsx" % safe_name

    def action_bks_print_payment_order(self):
        self.ensure_one()
        self._bks_check_payment_order_print_eligibility()
        wb = self._bks_build_payment_order_workbook()
        buffer = io.BytesIO()
        wb.save(buffer)
        raw = buffer.getvalue()
        filename = self._bks_payment_order_filename()
        if not self.genex_exported:
            self._mark_genex_exported()
        attachment = self.env["ir.attachment"].create(
            {
                "name": filename,
                "type": "binary",
                "raw": raw,
                "res_model": self._name,
                "res_id": self.id,
                "mimetype": (
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }
