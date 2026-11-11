# Part of Odoo. See LICENSE file for full copyright and licensing.

import io
import re
import zipfile

# Fichiers régénérés par openpyxl après édition des cellules.
_OPENPYXL_OVERRIDE_PARTS = frozenset(
    {
        "xl/worksheets/sheet1.xml",
        "xl/styles.xml",
    }
)

# La chaîne de calcul du modèle ne connaît que les formules d'origine :
# des formules déplacées ne seraient jamais calculées par Excel.
_CALC_CHAIN_PART = "xl/calcChain.xml"


def _strip_calc_chain_references(name, data):
    if name == "[Content_Types].xml":
        text = data.decode("utf-8")
        text = re.sub(r'<Override[^>]*PartName="/xl/calcChain\.xml"[^>]*/>', "", text)
        return text.encode("utf-8")
    if name == "xl/_rels/workbook.xml.rels":
        text = data.decode("utf-8")
        text = re.sub(r'<Relationship[^>]*Target="[^"]*calcChain\.xml"[^>]*/>', "", text)
        return text.encode("utf-8")
    if name == "xl/workbook.xml":
        text = data.decode("utf-8")
        if "<calcPr" in text:
            text = re.sub(r"\sfullCalcOnLoad=\"[^\"]*\"", "", text)
            text = text.replace("<calcPr", '<calcPr fullCalcOnLoad="1"', 1)
        return text.encode("utf-8")
    return data


def save_workbook_preserve_template(workbook, template_path):
    """Enregistre le classeur en conservant l'enveloppe OOXML du modèle.

    openpyxl seul produit un .xlsx incomplet (calcChain, printerSettings, etc.)
    que Excel refuse ou « répare ».
    """
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    output = io.BytesIO()
    with (
        zipfile.ZipFile(template_path) as template_zip,
        zipfile.ZipFile(buffer) as data_zip,
        zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as out_zip,
    ):
        for name in template_zip.namelist():
            if name == _CALC_CHAIN_PART:
                continue
            if name in _OPENPYXL_OVERRIDE_PARTS and name in data_zip.namelist():
                data = data_zip.read(name)
            else:
                data = template_zip.read(name)
            out_zip.writestr(name, _strip_calc_chain_references(name, data))
    output.seek(0)
    return output.getvalue()
