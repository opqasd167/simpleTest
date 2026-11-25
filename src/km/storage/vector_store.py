import re
from collections.abc import Callable
from pathlib import Path

import chromadb

from km.domain.models import DocChunk

DEFAULT_EMBEDDING = "default"


def _fastembed_function(model_name: str):
    """Chroma embedding function backed by fastembed (ONNX, no PyTorch); supports multilingual models."""
    from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
    from fastembed import TextEmbedding

    class FastEmbedFunction(EmbeddingFunction[Documents]):
        def __init__(self, name: str):
            self._name = name
            self._model = TextEmbedding(model_name=name)

        def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 (Chroma's parameter name)
            return [vec.tolist() for vec in self._model.embed(list(input))]

        @staticmethod
        def name() -> str:
            return "km_fastembed"

        def get_config(self) -> dict:
            return {"model_name": self._name}

        @staticmethod
        def build_from_config(config: dict) -> "FastEmbedFunction":
            return FastEmbedFunction(config["model_name"])

    return FastEmbedFunction(model_name)


def _callable_function(embed: Callable[[list[str]], list[list[float]]], label: str):
    """Chroma embedding function around any `texts -> vectors` callable (e.g. the company gateway)."""
    from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

    def _not_configured(_texts: list[str]) -> list[list[float]]:
        raise ValueError("km_external embeddings must be passed in explicitly (build_vector_store)")

    class CallableEmbeddingFunction(EmbeddingFunction[Documents]):
        def __init__(self, fn: Callable[[list[str]], list[list[float]]], model_name: str) -> None:
            self._fn, self._model_name = fn, model_name

        def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 (Chroma's parameter name)
            return self._fn(list(input))

        @staticmethod
        def name() -> str:
            return "km_external"

        def get_config(self) -> dict:
            return {"model_name": self._model_name}

        @staticmethod
        def build_from_config(config: dict) -> "CallableEmbeddingFunction":
            # Chroma round-trips the config; the real function is always supplied by our code
            return CallableEmbeddingFunction(_not_configured, config["model_name"])

    return CallableEmbeddingFunction(embed, label)


def collection_name(base: str, embedding_model: str) -> str:
    """Each embedding model gets its own collection: vectors from different models never mix."""
    if embedding_model == DEFAULT_EMBEDDING:
        return base
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", embedding_model.split("/")[-1]).strip("-").lower()
    return f"{base}__{slug}"[:60]


class VectorStore:
    """The only code that touches Chroma."""

    def __init__(self, path: Path, collection: str, embedding_model: str = DEFAULT_EMBEDDING,
                 embedder: Callable[[list[str]], list[list[float]]] | None = None):
        """embedder: an external `texts -> vectors` function; embedding_model then only names it."""
        client = chromadb.PersistentClient(path=str(path))
        kwargs = {}
        if embedder is not None:
            kwargs["embedding_function"] = _callable_function(embedder, embedding_model)
        elif embedding_model != DEFAULT_EMBEDDING:
            kwargs["embedding_function"] = _fastembed_function(embedding_model)
        self._col = client.get_or_create_collection(collection_name(collection, embedding_model), **kwargs)

    def upsert(self, ids: list[str], chunks: list[DocChunk]) -> None:
        if not chunks:
            return
        self._col.upsert(
            ids=ids,
            documents=[c.text for c in chunks],
            metadatas=[{"source": c.source, "location": c.location,
                        **{k: v for k, v in c.meta.items() if v is not None}} for c in chunks])

    def delete_source(self, source: str) -> None:
        """Remove every chunk of one file, so re-ingesting a shorter file leaves no stale chunks."""
        self._col.delete(where={"source": source})

    def search(self, query: str, k: int, where: dict | None = None) -> list[DocChunk]:
        """Top-k chunks by similarity, optionally restricted by a Chroma metadata filter."""
        total = self._col.count()
        if total == 0:
            return []
        r = self._col.query(query_texts=[query], n_results=min(k, total), where=where)
        return [DocChunk(source=m["source"], location=m["location"], text=d,
                         meta={key: v for key, v in m.items() if key not in ("source", "location")})
                for d, m in zip(r["documents"][0], r["metadatas"][0])]

    def count(self) -> int:
        return self._col.count()
