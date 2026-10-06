import base64
import io
import re
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

try:
    import openpyxl
    from openpyxl.styles import Font
except ImportError as err:
    openpyxl = None
    _openpyxl_import_error = err
else:
    _openpyxl_import_error = None

GENEX_HEADERS = (
    "Code Entreprise",
    "Code Agence",
    "Code Devise",
    "Code GL",
    "Num CIF",
    "Serie",
    "Vide",
    "Vide",
    "Vide",
    "Montant MAD",
    "Montant Devise Etrangère",
    "Taux",
    "Date Valeur",
    "Description (libellé de l'EC)",
    "Type Transaction",
    "Type EC",
    "Date Transaction",
    "Vide",
    "Compte (RIB)",
    "Vide",
    "Vide",
    "Référence",
)


class BksGenexExportWizard(models.TransientModel):
    _name = "bks.genex.export.wizard"
    _description = "Export fichier GENEX"

    date_from = fields.Date(string="Du", required=True)
    date_to = fields.Date(string="Au", required=True)
    journal_ids = fields.Many2many("account.journal", string="Journaux")
    move_ids = fields.Many2many(
        comodel_name="account.move",
        relation="bks_genex_export_wizard_move_rel",
        column1="wizard_id",
        column2="move_id",
        string="Écritures à exporter",
        help="Retirez les lignes à exclure de l'export GENEX.",
    )
    move_to_export_count = fields.Integer(
        string="Nombre d'écritures",
        compute="_compute_move_to_export_count",
    )
    file_data = fields.Binary(string="Fichier", readonly=True)
    file_name = fields.Char(string="Nom du fichier", readonly=True)
    bks_payment_export = fields.Boolean(
        string="Export depuis paiements",
        default=lambda self: bool(self.env.context.get("bks_genex_payment_export")),
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get("active_model")
        active_ids = self.env.context.get("active_ids") or []
        if active_model == "account.payment" and active_ids:
            payments = self.env["account.payment"].browse(active_ids)
            payments._bks_check_genex_export_eligibility()
            moves = payments.mapped("move_id")
            res["move_ids"] = [(6, 0, moves.ids)]
            dates = moves.mapped("date")
            if dates:
                res["date_from"] = min(dates)
                res["date_to"] = max(dates)
        elif active_model == "account.move" and active_ids:
            moves = self.env["account.move"].browse(active_ids).filtered(
                lambda m: m.state == "posted" and not m.genex_exported
            )
            res["move_ids"] = [(6, 0, moves.ids)]
            dates = moves.mapped("date")
            if dates:
                res["date_from"] = min(dates)
                res["date_to"] = max(dates)
        if not res.get("date_from"):
            today = fields.Date.context_today(self)
            res["date_from"] = today.replace(day=1)
            res["date_to"] = today
        if "move_ids" in fields_list and not res.get("move_ids"):
            res["move_ids"] = [
                (6, 0, self._search_moves_for_criteria(res).ids)
            ]
        return res

    @api.model
    def _search_moves_for_criteria(self, vals=None):
        vals = vals or {}
        date_from = vals.get("date_from")
        date_to = vals.get("date_to")
        if not date_from or not date_to:
            return self.env["account.move"]
        journal_ids = vals.get("journal_ids")
        if journal_ids and journal_ids[0][0] == 6:
            journal_id_list = journal_ids[0][2]
        else:
            journal_id_list = []
        domain = [
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            ("company_id", "in", self.env.companies.ids),
            ("state", "=", "posted"),
            ("genex_exported", "=", False),
        ]
        if journal_id_list:
            domain.append(("journal_id", "in", journal_id_list))
        return self.env["account.move"].search(domain, order="date, name, id")

    def _domain_moves_for_criteria(self):
        self.ensure_one()
        domain = [
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
            ("company_id", "in", self.env.companies.ids),
            ("state", "=", "posted"),
            ("genex_exported", "=", False),
        ]
        if self.journal_ids:
            domain.append(("journal_id", "in", self.journal_ids.ids))
        return domain

    def _is_payment_genex_export(self):
        self.ensure_one()
        return self.bks_payment_export

    def _check_payment_moves_for_export(self, moves):
        payments = self.env["account.payment"].search(
            [("move_id", "in", moves.ids)]
        )
        payment_by_move = {pay.move_id.id: pay for pay in payments}
        errors = []
        for move in moves:
            pay = payment_by_move.get(move.id)
            if not pay:
                errors.append(
                    _(
                        "%(move)s : export paiement GENEX réservé aux "
                        "écritures de paiement.",
                        move=move.display_name,
                    )
                )
        if errors:
            raise UserError("\n".join(errors))
        payments._bks_check_genex_export_eligibility()

    def action_reload_moves(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("La date de début doit être antérieure à la date de fin."))
        moves = self.env["account.move"].search(
            self._domain_moves_for_criteria(), order="date, name, id"
        )
        self.move_ids = [(6, 0, moves.ids)]
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
            "name": _("Export GENEX"),
        }

    @api.depends("move_ids")
    def _compute_move_to_export_count(self):
        for wizard in self:
            wizard.move_to_export_count = len(wizard.move_ids)

    def _get_moves(self, raise_if_empty=True):
        self.ensure_one()
        moves = self.move_ids
        already = moves.filtered("genex_exported")
        if already:
            raise UserError(
                _(
                    "Certaines écritures sont déjà exportées GENEX : %(names)s",
                    names=", ".join(already.mapped("name")[:10]),
                )
            )
        if self._is_payment_genex_export():
            self._check_payment_moves_for_export(moves)
            invalid_state = moves.filtered(lambda m: m.state != "draft")
            if invalid_state:
                raise UserError(
                    _(
                        "Les écritures de paiement à exporter GENEX doivent "
                        "être en brouillon : %(names)s",
                        names=", ".join(invalid_state.mapped("name")[:10]),
                    )
                )
        else:
            not_posted = moves.filtered(lambda m: m.state != "posted")
            if not_posted:
                raise UserError(
                    _(
                        "Seules les écritures comptabilisées peuvent être "
                        "exportées GENEX : %(names)s",
                        names=", ".join(not_posted.mapped("name")[:10]),
                    )
                )
        moves = moves.filtered(lambda m: not m.genex_exported)
        if not moves and raise_if_empty:
            raise UserError(_("Aucune écriture à exporter."))
        return moves

    @staticmethod
    def _gl_code(account):
        if account.genex_gl_code:
            return account.genex_gl_code
        digits = re.sub(r"\D", "", account.code or "")
        if not digits:
            return ""
        return digits[:6].zfill(6)[-6:]

    def _agency_code(self, line, company):
        distribution = line.analytic_distribution or {}
        if distribution:
            account_ids = [int(aid) for aid in distribution if str(aid).isdigit()]
            analytics = self.env["account.analytic.account"].browse(account_ids).exists()
            for analytic in analytics:
                if analytic.genex_agency_code:
                    return analytic.genex_agency_code
        return company.genex_default_agency_code or 1000

    @staticmethod
    def _short_reference(move):
        ref = (move.ref or move.payment_reference or move.name or "").strip()
        if not ref:
            return move.name or ""
        return ref.split()[0][:32]

    def _long_label(self, move):
        ref = self._short_reference(move)
        partner = move.partner_id.name or ""
        invoice_no = move.name or move.ref or ""
        desc = (
            move.narration
            or move.invoice_origin
            or move.ref
            or (move.line_ids[:1].name if move.line_ids else "")
            or ""
        )
        if isinstance(desc, str):
            desc = re.sub(r"<[^>]+>", " ", desc)
        desc = " ".join(str(desc).split())
        parts = [p for p in (ref, partner, f"FN°{invoice_no}", desc) if p]
        label = " ".join(parts)
        return label[:255]

    def _line_rows(self, move, company):
        rows = []
        currency_code = company.genex_currency_code or 504
        ec_type = company.genex_ec_type or 563
        company_code = company.genex_company_code or 1
        ref_short = self._short_reference(move)
        long_label = self._long_label(move)
        move_date = move.date
        partner = move.partner_id
        cif = partner.genex_cif or 0 if partner else 0
        rib = move._get_genex_rib()

        lines = move.line_ids.filtered(
            lambda line: line.display_type not in ("line_section", "line_subsection", "line_note")
            and line.account_id
        )
        for line in lines:
            amount_mad = abs(line.balance)
            if company.currency_id.is_zero(amount_mad):
                continue
            amount_currency = None
            rate = None
            if (
                line.currency_id
                and line.currency_id != company.currency_id
                and not line.currency_id.is_zero(line.amount_currency)
            ):
                amount_currency = abs(line.amount_currency)
                if line.currency_rate:
                    rate = line.currency_rate

            serie = 1 if cif else 0
            rows.append(
                (
                    company_code,
                    self._agency_code(line, company),
                    currency_code,
                    self._gl_code(line.account_id),
                    cif,
                    serie,
                    None,
                    None,
                    None,
                    amount_mad,
                    amount_currency,
                    rate,
                    move_date,
                    ref_short,
                    None,
                    ec_type,
                    move_date,
                    long_label,
                    rib,
                    None,
                    None,
                    ref_short,
                )
            )
        return rows

    @staticmethod
    def _genex_cell_value(value):
        """Évite d'écrire False/True dans Excel (affichés FAUX/ VRAI)."""
        if value is False or value is True:
            return None
        return value

    def _build_workbook(self, moves):
        if not openpyxl:
            raise UserError(
                _("Bibliothèque Python openpyxl requise : %s") % _openpyxl_import_error
            )
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "GENEX Odoo"
        header_font = Font(bold=True)
        for col, title in enumerate(GENEX_HEADERS, start=1):
            cell = ws.cell(row=1, column=col, value=title)
            cell.font = header_font

        row_idx = 2
        for move in moves:
            company = move.company_id
            for row in self._line_rows(move, company):
                for col, value in enumerate(row, start=1):
                    if isinstance(value, datetime):
                        value = value.date()
                    ws.cell(
                        row=row_idx,
                        column=col,
                        value=self._genex_cell_value(value),
                    )
                row_idx += 1
        return wb

    def action_export_genex(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("La date de début doit être antérieure à la date de fin."))

        moves = self._get_moves()
        wb = self._build_workbook(moves)
        moves._mark_genex_exported()
        buffer = io.BytesIO()
        wb.save(buffer)
        filename = "GENEX_%s_%s.xlsx" % (
            self.date_from.isoformat(),
            self.date_to.isoformat(),
        )
        if self.move_ids and len(self.move_ids) == 1:
            name = self.move_ids.name or str(self.move_ids.id)
            filename = "GENEX_%s.xlsx" % re.sub(r"[^\w\-]+", "_", name)

        self.write(
            {
                "file_data": base64.b64encode(buffer.getvalue()),
                "file_name": filename,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
            "name": _("Export GENEX"),
        }
