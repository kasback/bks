# Part of Odoo. See LICENSE file for full copyright and licensing.

import io
import zipfile
from xml.sax.saxutils import escape


def render_docx_template(template_path, replacements):
    """Remplace des marqueurs texte dans word/document.xml."""
    output = io.BytesIO()
    with (
        zipfile.ZipFile(template_path) as template_zip,
        zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as out_zip,
    ):
        for item in template_zip.infolist():
            data = template_zip.read(item.filename)
            if item.filename == "word/document.xml":
                text = data.decode("utf-8")
                for marker, value in replacements.items():
                    text = text.replace(
                        marker, escape(str(value or ""), {'"': "&quot;"})
                    )
                data = text.encode("utf-8")
            out_zip.writestr(item, data)
    output.seek(0)
    return output.getvalue()
