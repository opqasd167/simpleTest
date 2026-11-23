import logging
from functools import lru_cache
from pathlib import Path

from docx import Document
from docx.table import Table
from pypdf import PdfReader

SUPPORTED = {".pdf", ".docx"}
log = logging.getLogger(__name__)


def _docx_text(path: Path) -> str:
    """Paragraphs AND tables, in document order. Table rows become 'a | b | c'."""
    lines = []
    for block in Document(path).iter_inner_content():
        if isinstance(block, Table):
            for row in block.rows:
                lines.append(" | ".join(cell.text.strip() for cell in row.cells))
        else:
            lines.append(block.text)
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _ocr_engine():
    from rapidocr_onnxruntime import RapidOCR  # Chinese + English models, runs offline on CPU
    return RapidOCR()


def ocr_pdf_page(path: Path, index: int, dpi: int = 200) -> str:
    """Render one PDF page to an image and read its text with OCR."""
    import pymupdf

    with pymupdf.open(path) as doc:
        png = doc[index].get_pixmap(dpi=dpi).tobytes("png")
    result, _ = _ocr_engine()(png)
    return "\n".join(line[1] for line in (result or []))


def load_file(path: Path, ocr: bool = False, ocr_min_chars: int = 20) -> list[tuple[str, str]]:
    """Return (location, text) pairs: one per PDF page, one per Word file.

    With ocr=True, a PDF page with almost no extractable text (a scan) is read with OCR instead."""
    if path.suffix.lower() == ".pdf":
        pages = []
        for i, page in enumerate(PdfReader(path).pages):
            text = page.extract_text() or ""
            if ocr and len(text.strip()) < ocr_min_chars:
                try:
                    text = ocr_pdf_page(path, i)
                    log.info("OCR used for %s page %d (%d chars)", path.name, i + 1, len(text))
                except ImportError:
                    log.warning("%s page %d looks scanned, but OCR is not installed "
                                "(pip install -e \".[ocr]\")", path.name, i + 1)
            pages.append((f"page {i + 1}", text))
        return pages
    if path.suffix.lower() == ".docx":
        return [("body", _docx_text(path))]
    raise ValueError(f"Unsupported file type: {path.name}")
