#!/usr/bin/env python3
"""Import plan comptable BKS depuis Plan_comptable_final_Odoo19_GL_6_chiffres.xlsx (onglet Import_Odoo19)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import openpyxl

XLSX_PATH = Path(
    "/Users/macbookpro/Documents/osisoftware/bks/assets/Plan_comptable_final_Odoo19_GL_6_chiffres.xlsx"
)
SHEET = "Import_Odoo19"
BATCH_SIZE = 100

_logger = logging.getLogger(__name__)


def load_rows(path: Path = XLSX_PATH) -> list[tuple[str, str, str]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[SHEET]
    rows: list[tuple[str, str, str]] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        code, name, account_type = row[0], row[1], row[2]
        if not code:
            continue
        code = str(code).strip()
        name = (name or "").strip()
        account_type = (account_type or "").strip()
        if not name or not account_type:
            raise ValueError(f"Ligne invalide pour le code {code!r}")
        rows.append((code, name, account_type))
    if not rows:
        raise ValueError("Aucune ligne à importer")
    return rows


def _existing_by_code(env, company):
    Account = env["account.account"].with_company(company)
    by_code = {}
    for acc in Account.with_context(active_test=False).search([("company_ids", "in", company.id)]):
        if acc.code:
            by_code.setdefault(acc.code, acc)
    return Account, by_code


def run(env):
    company = env.company
    Account, existing = _existing_by_code(env, company)
    ctx = {
        "tracking_disable": True,
        "mail_create_nolog": True,
        "mail_notrack": True,
    }

    rows = load_rows()
    to_create = []
    updated = 0
    skipped = 0

    for code, name, account_type in rows:
        acc = existing.get(code)
        if not acc:
            acc = Account.search([("code", "=", code)], limit=1)
            if acc:
                existing[code] = acc
        if acc:
            vals = {}
            if acc.name != name:
                vals["name"] = name
            if acc.account_type != account_type:
                vals["account_type"] = account_type
            if vals:
                acc.with_context(**ctx).write(vals)
                updated += 1
            else:
                skipped += 1
            continue
        to_create.append(
            {
                "name": name,
                "code": code,
                "account_type": account_type,
                "company_ids": [(6, 0, [company.id])],
            }
        )

    created = 0
    errors: list[str] = []
    for vals in to_create:
        try:
            acc = Account.with_context(**ctx).create([vals])
            existing[vals["code"]] = acc
            created += 1
            if created % BATCH_SIZE == 0:
                env.cr.commit()
        except Exception as exc_one:
            env.cr.rollback()
            acc = Account.search([("code", "=", vals["code"])], limit=1)
            if acc:
                existing[vals["code"]] = acc
                skipped += 1
            else:
                errors.append(f"{vals['code']}: {exc_one}")
    env.cr.commit()

    excel_codes = {code for code, _, _ in rows}
    present = sum(1 for code in excel_codes if code in existing)
    total = Account.search_count([("company_ids", "in", company.id)])
    return {
        "excel_rows": len(rows),
        "created": created,
        "updated": updated,
        "unchanged": skipped,
        "excel_codes_present": present,
        "total_accounts": total,
        "errors": errors,
    }


if __name__ == "__main__":
    print("Ce script doit être exécuté via odoo-bin shell.", file=sys.stderr)
    sys.exit(1)
