"""
PDF text extraction.

Primary: pypdfium2 (Chrome's PDF engine) - fast, robust, does not get
stuck parsing complex vector graphics (icons, decorative borders, etc.
commonly found in Canva-style resume templates).

Fallback: pdfplumber - used only if pypdfium2 extracts no text at all
(e.g. unusual/older PDF encodings), since some PDFs parse better with it.
"""

import pdfplumber
import pypdfium2 as pdfium


def _extract_with_pypdfium2(file) -> str:
    file.seek(0)
    data = file.read()
    pdf = pdfium.PdfDocument(data)
    text_parts = []
    try:
        for page in pdf:
            textpage = page.get_textpage()
            text_parts.append(textpage.get_text_range())
            textpage.close()
            page.close()
    finally:
        pdf.close()
    return "\n".join(text_parts)


def _extract_with_pdfplumber(file) -> str:
    file.seek(0)
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_text_from_pdf(file) -> str:
    # Try the fast, robust extractor first.
    try:
        text = _extract_with_pypdfium2(file)
    except Exception:
        text = ""

    if text.strip():
        return text

    # Fallback for PDFs pypdfium2 couldn't get text from.
    try:
        text = _extract_with_pdfplumber(file)
    except Exception:
        text = ""

    return text