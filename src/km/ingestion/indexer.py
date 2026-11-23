import logging
from pathlib import Path

from km.domain.models import DocChunk
from km.ingestion.chunker import chunk_text
from km.ingestion.loaders import SUPPORTED, load_file
from km.storage.vector_store import VectorStore

log = logging.getLogger(__name__)


class Indexer:
    def __init__(self, store: VectorStore, chunk_size: int, overlap: int):
        self._store, self._size, self._overlap = store, chunk_size, overlap

    def index_folder(self, folder: Path) -> int:
        total = 0
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in SUPPORTED:
                log.warning("Skipping unsupported file %s", path.name)
                continue
            ids, chunks = [], []
            for loc, text in load_file(path):
                if not text.strip():
                    log.warning("No text extracted from %s (%s); scanned PDF?", path.name, loc)
                for n, piece in enumerate(chunk_text(text, self._size, self._overlap)):
                    ids.append(f"{path.name}|{loc}|{n}")
                    chunks.append(DocChunk(source=path.name, location=loc, text=piece))
            self._store.delete_source(path.name)
            self._store.upsert(ids, chunks)
            log.info("Indexed %d chunks from %s", len(chunks), path.name)
            total += len(chunks)
        return total
