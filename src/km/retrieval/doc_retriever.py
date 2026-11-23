from km.domain.models import DocChunk
from km.storage.vector_store import VectorStore


class DocRetriever:
    def __init__(self, store: VectorStore, top_k: int):
        self._store, self._k = store, top_k

    def retrieve(self, question: str) -> list[DocChunk]:
        return self._store.search(question, self._k)
