"""Composition root: builds every object from Settings. Used by both the API and the CLI."""
from km.config import Settings
from km.generation.answer_writer import AnswerWriter
from km.ingestion.indexer import Indexer
from km.llm.base import LLMClient
from km.retrieval.doc_retriever import DocRetriever
from km.retrieval.sql_retriever import SqlRetriever
from km.routing.intent_router import IntentRouter
from km.services.qa_service import QAService
from km.storage.sql_store import SqlStore
from km.storage.vector_store import VectorStore
from km.validation.groundedness import GroundednessValidator


def build_llm(s: Settings) -> LLMClient:
    if s.llm_provider == "grok_cli":
        from km.llm.grok_cli_client import GrokCliClient
        return GrokCliClient(s)
    from km.llm.anthropic_client import AnthropicClient
    return AnthropicClient(s)


def build_qa_service(s: Settings, llm: LLMClient | None = None) -> QAService:
    llm = llm or build_llm(s)
    sql_store = SqlStore(s.sqlite_path)
    vectors = VectorStore(s.chroma_dir, s.chroma_collection, s.embedding_model)
    return QAService(
        router=IntentRouter(llm),
        docs=DocRetriever(vectors, s.top_k),
        sql=SqlRetriever(llm, sql_store, s.sql_max_rows),
        writer=AnswerWriter(llm),
        validator=GroundednessValidator(llm),
        sql_store=sql_store)


def build_indexer(s: Settings) -> Indexer:
    return Indexer(VectorStore(s.chroma_dir, s.chroma_collection, s.embedding_model),
                   s.chunk_size, s.chunk_overlap, ocr=s.ocr_enabled, ocr_min_chars=s.ocr_min_chars)


def build_judge_llm(s: Settings) -> LLMClient:
    """The grading model for benchmarks. Use a different model than the one being tested
    (KM_JUDGE_PROVIDER / KM_JUDGE_MODEL), so the system does not grade its own homework."""
    if s.judge_provider is None and s.judge_model is None:
        return build_llm(s)
    provider = s.judge_provider or s.llm_provider
    model_field = "grok_model" if provider == "grok_cli" else "llm_model"
    update = {"llm_provider": provider}
    if s.judge_model:
        update[model_field] = s.judge_model
    return build_llm(s.model_copy(update=update))
