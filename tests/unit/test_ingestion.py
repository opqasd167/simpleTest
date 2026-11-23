from pathlib import Path

import pytest

from km.ingestion.chunker import chunk_text
from km.ingestion.loaders import load_file

DOCS = Path("data/raw/docs")


def test_chunks_overlap_and_cover_text():
    text = "".join(str(i % 10) for i in range(2000))
    chunks = chunk_text(text, size=800, overlap=150)
    assert all(len(c) <= 800 for c in chunks)
    assert chunks[0][-150:] == chunks[1][:150]   # overlap is kept
    assert chunks[-1].endswith(text[-10:])        # nothing lost at the end


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        chunk_text("abc", size=100, overlap=100)


def test_word_loader_reads_tables():
    """The VP approval rule only exists inside a Word table."""
    [(location, text)] = load_file(DOCS / "Travel_and_Expense_Policy.docx")
    assert location == "body"
    assert "Over $1,500 per trip | Vice President (VP), before booking" in text


def test_pdf_loader_returns_one_entry_per_page():
    pages = load_file(DOCS / "Leave_Policy.pdf")
    assert [loc for loc, _ in pages] == ["page 1", "page 2", "page 3"]
    assert "20 working days" in pages[0][1]
