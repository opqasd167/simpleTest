from pathlib import Path

import chromadb

from km.domain.models import DocChunk


class VectorStore:
    """The only code that touches Chroma."""

    def __init__(self, path: Path, collection: str):
        client = chromadb.PersistentClient(path=str(path))
        self._col = client.get_or_create_collection(collection)

    def upsert(self, ids: list[str], chunks: list[DocChunk]) -> None:
        if not chunks:
            return
        self._col.upsert(
            ids=ids,
            documents=[c.text for c in chunks],
            metadatas=[{"source": c.source, "location": c.location} for c in chunks])

    def delete_source(self, source: str) -> None:
        """Remove every chunk of one file, so re-ingesting a shorter file leaves no stale chunks."""
        self._col.delete(where={"source": source})

    def search(self, query: str, k: int) -> list[DocChunk]:
        if self._col.count() == 0:
            return []
        r = self._col.query(query_texts=[query], n_results=min(k, self._col.count()))
        return [DocChunk(source=m["source"], location=m["location"], text=d)
                for d, m in zip(r["documents"][0], r["metadatas"][0])]

    def count(self) -> int:
        return self._col.count()
