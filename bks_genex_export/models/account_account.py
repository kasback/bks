from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

_GENEX_KEY_FIELDS = {
    "genex_agency_code",
    "genex_currency_code",
    "genex_cif",
    "genex_sequence",
}


class AccountAccount(models.Model):
    _inherit = "account.account"

    genex_agency_code = fields.Integer(
        string="Code agence",
        help="Code agence iMal (BRANCH_CODE). Ex. : 1000.",
    )
    genex_currency_code = fields.Integer(
        string="Code devise",
        help="Code devise iMal (CURRENCY_CODE). Ex. : 504 (MAD).",
    )
    genex_cif = fields.Integer(
        string="CIF",
        help="Numéro CIF iMal (CIF_SUB_NO). 0 si non applicable.",
    )
    genex_sequence = fields.Integer(
        string="Séquence",
        help="Séquence iMal (SL_NO). Ex. : 0 ou 1.",
    )
    genex_full_code = fields.Char(
        string="Code complet",
        compute="_compute_genex_full_code",
        search="_search_genex_full_code",
        help="Code agence.code devise.code du compte.CIF.séquence "
        "(ex. 1000.504.367105.0.1). Renseigné si agence et devise sont définies.",
    )

    @api.depends(
        "code",
        "genex_agency_code",
        "genex_currency_code",
        "genex_cif",
        "genex_sequence",
    )
    @api.depends_context("company")
    def _compute_genex_full_code(self):
        for account in self:
            code = (account.code or "").strip()
            if account.genex_agency_code and account.genex_currency_code and code:
                account.genex_full_code = ".".join(
                    str(part)
                    for part in (
                        account.genex_agency_code,
                        account.genex_currency_code,
                        code,
                        account.genex_cif or 0,
                        account.genex_sequence or 0,
                    )
                )
            else:
                account.genex_full_code = False

    def _search_genex_full_code(self, operator, value):
        candidates = self.with_context(active_test=False).search(
            [("genex_agency_code", "!=", 0), ("genex_currency_code", "!=", 0)]
        )
        if operator in ("=", "in"):
            values = value if isinstance(value, (list, tuple, set)) else [value]
            ids = candidates.filtered(lambda a: a.genex_full_code in values).ids
            return [("id", "in", ids)]
        if operator in ("!=", "not in"):
            values = value if isinstance(value, (list, tuple, set)) else [value]
            ids = candidates.filtered(lambda a: a.genex_full_code in values).ids
            return [("id", "not in", ids)]
        needle = (value or "").replace("%", "").lower() if isinstance(value, str) else ""
        matched = candidates.filtered(
            lambda a: needle in (a.genex_full_code or "").lower()
        ).ids
        if operator in ("not ilike", "not like"):
            return [("id", "not in", matched)]
        return [("id", "in", matched)]

    # ------------------------------------------------------------------
    # Unicité : sur le « Code complet » (si renseigné), sinon sur le code
    # ------------------------------------------------------------------
    def _genex_unique_key(self):
        self.ensure_one()
        return self.genex_full_code or self.code

    def _ensure_code_is_unique(self):
        """Remplace le contrôle standard : deux comptes peuvent partager le
        même code Odoo s'ils ont un « Code complet » différent (séquence)."""
        for account in self.sudo():
            for company in account.company_ids.root_id:
                if not account.with_company(company).code:
                    raise ValidationError(
                        _("The code must be set for every company to which this account belongs.")
                    )

        account_ids_by_company = defaultdict(list)
        for account in self.sudo():
            for company in account.company_ids:
                account_ids_by_company[company].append(account.id)

        for company, account_ids in account_ids_by_company.items():
            accounts = (
                self.browse(account_ids).with_prefetch(self.ids).sudo().with_company(company)
            )
            keys = set()
            duplicates = set()
            for account in accounts:
                key = account._genex_unique_key()
                if key in keys:
                    duplicates.add(key)
                keys.add(key)
            if not duplicates:
                codes = list({account.code for account in accounts})
                others = (
                    self.with_company(company)
                    .sudo()
                    .with_context(active_test=False)
                    .search(
                        [
                            ("code", "in", codes),
                            ("id", "not in", self.ids),
                            "|",
                            ("company_ids", "parent_of", company.ids),
                            ("company_ids", "child_of", company.ids),
                        ]
                    )
                )
                duplicates = {
                    other._genex_unique_key()
                    for other in others
                    if other._genex_unique_key() in keys
                }
            if duplicates:
                raise ValidationError(
                    _(
                        "Account codes must be unique. You can't create accounts "
                        "with these duplicate codes: %s",
                        ", ".join(sorted(duplicates)),
                    )
                )

    def write(self, vals):
        res = super().write(vals)
        if (
            _GENEX_KEY_FIELDS & vals.keys()
            and not {"company_ids", "code", "code_mapping_ids"} & vals.keys()
            and not self.env.context.get("defer_account_code_checks")
        ):
            self._ensure_code_is_unique()
        return res

    # ------------------------------------------------------------------
    # Duplication : même code Odoo, séquence incrémentée
    # ------------------------------------------------------------------
    def _genex_next_sequence(self, taken=None):
        """Prochaine séquence libre pour (agence, devise, code, CIF)."""
        self.ensure_one()
        siblings = (
            self.sudo()
            .with_context(active_test=False)
            .search(
                [
                    ("code", "=", self.code),
                    ("genex_agency_code", "=", self.genex_agency_code),
                    ("genex_currency_code", "=", self.genex_currency_code),
                    ("genex_cif", "=", self.genex_cif),
                ]
            )
        )
        used = set(siblings.mapped("genex_sequence")) | set(taken or ())
        return max(used or {0}) + 1

    def copy_data(self, default=None):
        vals_list = super().copy_data(default)
        default = default or {}
        taken = defaultdict(set)
        for account, vals in zip(self, vals_list):
            if (
                not account.genex_full_code
                or "code" in default
                or "code_mapping_ids" in default
                or "genex_sequence" in default
            ):
                continue
            key = (
                account.code,
                account.genex_agency_code,
                account.genex_currency_code,
                account.genex_cif,
            )
            sequence = account._genex_next_sequence(taken[key])
            taken[key].add(sequence)
            vals["genex_sequence"] = sequence
            # Conserver le même code Odoo pour chaque société
            vals["code_mapping_ids"] = [
                Command.create(
                    {
                        "company_id": company.id,
                        "code": account.with_company(company).code
                        or account.with_company(account.company_ids[0]).code,
                    }
                )
                for company in account.company_ids
            ]
        return vals_list

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        if (
            domain is not NotImplemented
            and operator in ("ilike", "like", "=ilike", "=like")
            and isinstance(value, str)
            and "." in value
        ):
            return Domain(domain) | Domain("genex_full_code", "ilike", value)
        return domain

    @api.depends(
        "genex_agency_code",
        "genex_currency_code",
        "genex_cif",
        "genex_sequence",
    )
    def _compute_display_name(self):
        super()._compute_display_name()
        for account in self:
            full_code = account.genex_full_code
            if full_code and account.display_name:
                account.display_name = "[%s] %s" % (full_code, account.display_name)
