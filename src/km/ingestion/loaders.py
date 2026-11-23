from pathlib import Path

from docx import Document
from docx.table import Table
from pypdf import PdfReader

SUPPORTED = {".pdf", ".docx"}


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


def load_file(path: Path) -> list[tuple[str, str]]:
    """Return (location, text) pairs: one per PDF page, one per Word file."""
    if path.suffix.lower() == ".pdf":
        return [(f"page {i + 1}", page.extract_text() or "")
                for i, page in enumerate(PdfReader(path).pages)]
    if path.suffix.lower() == ".docx":
        return [("body", _docx_text(path))]
    raise ValueError(f"Unsupported file type: {path.name}")
