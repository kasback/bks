# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
from io import BytesIO

from odoo import models


class PurchaseOrderBksXlsx(models.AbstractModel):
    _name = "report.bks_purchase_approval.report_purchase_order_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Bon de commande BKS (Excel)"

    def generate_xlsx_report(self, workbook, data, orders):
        for order in orders:
            self._bks_write_po_sheet(workbook, order)

    def _bks_write_po_sheet(self, workbook, order):
        bks = order._bks_po_print_data()
        sheet_name = (order.name or "BDC")[:31]
        sheet = workbook.add_worksheet(sheet_name)
        sheet.set_paper(9)
        sheet.fit_to_pages(1, 1)
        sheet.set_margins(left=0.5, right=0.5, top=0.4, bottom=0.4)
        sheet.hide_gridlines(2)
        sheet.set_column("A:A", 41.25)
        sheet.set_column("B:B", 12)
        sheet.set_column("C:C", 18)
        sheet.set_column("D:D", 18)
        sheet.set_column("E:E", 12)

        font = "Arial"
        fmt_base = {"font_name": font, "font_size": 9, "font_color": "black"}
        fmt_center = workbook.add_format({**fmt_base, "align": "center"})
        fmt_left = workbook.add_format({**fmt_base, "align": "left"})
        fmt_city = workbook.add_format({**fmt_base, "align": "center"})
        fmt_partner = workbook.add_format(
            {
                **fmt_base,
                "font_size": 12,
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
            }
        )
        fmt_service = workbook.add_format(
            {**fmt_base, "font_size": 11, "bold": True}
        )
        fmt_title = workbook.add_format({**fmt_base, "bold": True})
        fmt_objet = workbook.add_format(
            {**fmt_base, "font_size": 10, "bold": True, "valign": "vcenter"}
        )
        fmt_intro = workbook.add_format({**fmt_base, "align": "left", "valign": "top"})
        header = {
            **fmt_base,
            "font_size": 10,
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,
            "bg_color": "#99CC00",
            "border": 1,
        }
        fmt_header = workbook.add_format(header)
        cell = {
            **fmt_base,
            "font_size": 10,
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,
            "border": 1,
        }
        fmt_cell = workbook.add_format(cell)
        fmt_cell_name = workbook.add_format({**cell, "font_size": 11})
        fmt_money = workbook.add_format({**cell, "num_format": "#,##0.00"})
        fmt_qty = workbook.add_format({**cell, "num_format": "0.00"})
        fmt_total_lbl = workbook.add_format({**cell, "bold": True})
        fmt_total = workbook.add_format(
            {**cell, "bold": True, "num_format": "#,##0.00"}
        )
        fmt_comment_title = workbook.add_format(
            {**fmt_base, "bold": True, "align": "left", "valign": "vcenter"}
        )
        fmt_comment = workbook.add_format(
            {
                **fmt_base,
                "font_size": 10,
                "align": "left",
                "valign": "vcenter",
                "text_wrap": True,
                "border": 1,
            }
        )
        fmt_sign_name = workbook.add_format(
            {
                **fmt_base,
                "font_size": 11,
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
            }
        )
        fmt_sign_title = workbook.add_format(
            {
                **fmt_base,
                "font_size": 10,
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
            }
        )

        sheet.set_row(0, 18)
        sheet.set_row(3, 32)
        sheet.set_row(5, 28)
        sheet.set_row(10, 20)
        sheet.merge_range("C3:D3", bks["city_date"], fmt_city)
        sheet.merge_range("C4:D4", bks["partner_name"], fmt_partner)
        sheet.merge_range("C5:D5", bks["partner_city"], fmt_center)
        sheet.write("A7", bks["service"], fmt_service)
        sheet.write("A9", bks["title"], fmt_title)
        objet = bks["objet"] and f"Objet : {bks['objet']}" or "Objet :"
        sheet.write("A11", objet, fmt_objet)
        sheet.write("A13", f"REFERENCE : {bks['reference']}", fmt_title)
        sheet.merge_range("A16:C16", bks["intro"], fmt_intro)

        sheet.set_row(17, 42)
        sheet.write("A18", "Désignation/Article/Référence", fmt_header)
        sheet.write("B18", "Quantité", fmt_header)
        sheet.write("C18", "Prix Unitaire DH / HT", fmt_header)
        sheet.write("D18", "Prix Total DH / HT", fmt_header)

        row = 18
        first_amount_row = 19
        for line in bks["lines"]:
            sheet.set_row(row, 36)
            sheet.write(row, 0, line["name"], fmt_cell_name)
            qty = line["qty"]
            sheet.write_number(row, 1, qty, fmt_qty)
            sheet.write_number(row, 2, line["price_unit"], fmt_money)
            sheet.write_number(row, 3, line["price_subtotal"], fmt_money)
            row += 1
        last_amount_row = row
        if not bks["lines"]:
            sheet.set_row(row, 36)
            sheet.write(row, 0, "", fmt_cell_name)
            sheet.write(row, 1, "", fmt_cell)
            sheet.write(row, 2, "", fmt_cell)
            sheet.write(row, 3, "", fmt_cell)
            last_amount_row = row + 1
            first_amount_row = 19
            row += 1

        sheet.set_row(row, 28)
        sheet.write(row, 2, "TOTAL HT", fmt_total_lbl)
        if bks["lines"]:
            sheet.write_formula(
                row,
                3,
                f"=SUM(D{first_amount_row}:D{last_amount_row})",
                fmt_total,
                bks["amount_untaxed"],
            )
        else:
            sheet.write_number(row, 3, 0, fmt_total)
        row += 2
        sheet.write(row, 0, bks["comment_title"], fmt_comment_title)
        row += 1
        sheet.set_row(row, 50)
        sheet.merge_range(row, 0, row + 1, 3, bks["comment"], fmt_comment)
        row += 3
        sheet.write(row, 0, bks["conditions_title"], fmt_comment_title)
        row += 1
        sheet.write(
            row, 0, f"    Date de livraison : {bks['delivery_date']}", fmt_left
        )
        row += 1
        sheet.write(
            row, 0, f"    Lieu de livraison : {bks['delivery_place']}", fmt_left
        )
        row += 3
        sheet.set_row(row, 22)
        sheet.write(row, 0, bks["closing"], fmt_left)
        row += 4
        sheet.set_row(row, 28)
        sheet.write(row, 0, bks["sign_left_name"], fmt_sign_name)
        sheet.merge_range(row, 1, row, 4, bks["sign_right_name"], fmt_sign_name)
        row += 1
        sheet.write(row, 0, bks["sign_left_title"], fmt_sign_title)
        sheet.merge_range(row, 1, row, 4, bks["sign_right_title"], fmt_sign_title)

        self._bks_insert_logo(sheet, bks.get("logo"))

    def _bks_insert_logo(self, sheet, logo_b64):
        if not logo_b64:
            return
        raw = base64.b64decode(logo_b64)
        filename = "logo.png" if raw.startswith(b"\x89PNG") else "logo.jpg"
        sheet.insert_image(
            0,
            0,
            filename,
            {
                "image_data": BytesIO(raw),
                "x_offset": 4,
                "y_offset": 2,
                "x_scale": 0.7,
                "y_scale": 0.7,
                "object_position": 1,
            },
        )
