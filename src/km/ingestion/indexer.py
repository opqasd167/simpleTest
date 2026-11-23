import json
import logging
from pathlib import Path

from km.domain.models import DocChunk
from km.ingestion.chunker import chunk_text
from km.ingestion.loaders import SUPPORTED, load_file
from km.storage.vector_store import VectorStore

log = logging.getLogger(__name__)
METADATA_FILE = "_metadata.json"
OPEN_END = 99991231


def _date_int(value: str | None) -> int | None:
    return int(value.replace("-", "")) if value else None


def load_metadata(folder: Path) -> dict[str, dict]:
    """Optional <docs>/_metadata.json: per-file status, effective dates, region, language.

    {"Travel_and_Expense_Policy_2025.docx": {"status": "superseded", "effective_from": "2025-01-01",
                                            "effective_to": "2025-12-31", "region": "group"}}
    Dates are stored as YYYYMMDD integers so Chroma can filter on them with $lte/$gte."""
    path = folder / METADATA_FILE
    if not path.exists():
        return {}
    out = {}
    for name, m in json.loads(path.read_text(encoding="utf-8")).items():
        meta = dict(m)
        if "effective_from" in meta:
            meta["effective_from"] = _date_int(meta["effective_from"])
            meta["effective_to"] = _date_int(meta.get("effective_to")) or OPEN_END
        out[name] = meta
    return out


class Indexer:
    def __init__(self, store: VectorStore, chunk_size: int, overlap: int,
                 ocr: bool = False, ocr_min_chars: int = 20):
        self._store, self._size, self._overlap = store, chunk_size, overlap
        self._ocr, self._ocr_min = ocr, ocr_min_chars

    def index_folder(self, folder: Path) -> int:
        metadata = load_metadata(folder)
        total = 0
        for path in sorted(folder.iterdir()):
            if path.name == METADATA_FILE:
                continue
            if path.suffix.lower() not in SUPPORTED:
                log.warning("Skipping unsupported file %s", path.name)
                continue
            meta = metadata.get(path.name, {})
            ids, chunks = [], []
            for loc, text in load_file(path, ocr=self._ocr, ocr_min_chars=self._ocr_min):
                if not text.strip():
                    log.warning("No text extracted from %s (%s); scanned PDF without OCR?", path.name, loc)
                for n, piece in enumerate(chunk_text(text, self._size, self._overlap)):
                    ids.append(f"{path.name}|{loc}|{n}")
                    chunks.append(DocChunk(source=path.name, location=loc, text=piece, meta=meta))
            self._store.delete_source(path.name)
            self._store.upsert(ids, chunks)
            log.info("Indexed %d chunks from %s", len(chunks), path.name)
            total += len(chunks)
        return total
