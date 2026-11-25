"""Composition root: builds every object from Settings. Used by both the API and the CLI."""
from km.config import ConfigError, Settings
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


GATEWAY_EMBEDDING_PREFIX = "gateway:"


def build_llm(s: Settings) -> LLMClient:
    if s.llm_provider == "grok_cli":
        from km.llm.grok_cli_client import GrokCliClient
        return GrokCliClient(s)
    if s.llm_provider == "gateway":
        from km.llm.gateway_client import GatewayClient
        return GatewayClient(s)
    from km.llm.anthropic_client import AnthropicClient
    return AnthropicClient(s)


_EMBEDDING_HELP = ("For the company gateway set KM_EMBEDDING_MODEL=gateway:<embedding model name> "
                   "(e.g. gateway:uae) and put the URL in KM_GATEWAY_BASE_URL.")


def check_embedding_config(s: Settings) -> None:
    """Catch the usual KM_EMBEDDING_MODEL mix-ups before a library fails with a confusing error."""
    model = s.embedding_model.strip()
    if model.startswith(("http://", "https://")):
        raise ConfigError(f"KM_EMBEDDING_MODEL is a URL ({model}). {_EMBEDDING_HELP}")
    if model.startswith(GATEWAY_EMBEDDING_PREFIX):
        name = model[len(GATEWAY_EMBEDDING_PREFIX):]
        if not name:
            raise ConfigError(f"KM_EMBEDDING_MODEL=gateway: has no model name. {_EMBEDDING_HELP}")
        if name.startswith(("http://", "https://")):
            raise ConfigError(f"KM_EMBEDDING_MODEL has a URL after 'gateway:'. {_EMBEDDING_HELP}")
        if not s.gateway_embed_url:
            raise ConfigError("KM_EMBEDDING_MODEL uses the gateway, but KM_GATEWAY_BASE_URL is not set "
                              "(check the spelling in .env), so there is no embeddings URL.")
        return
    if s.gateway_model and model == s.gateway_model:
        raise ConfigError(f"KM_EMBEDDING_MODEL={model} is your chat model (KM_GATEWAY_MODEL), not an "
                          f"embedding model. {_EMBEDDING_HELP}")


def build_vector_store(s: Settings) -> VectorStore:
    """KM_EMBEDDING_MODEL=gateway:<model> embeds through the company AI gateway; anything else
    is a local model (Chroma default or fastembed)."""
    check_embedding_config(s)
    embedder = None
    if s.embedding_model.startswith(GATEWAY_EMBEDDING_PREFIX):
        from km.llm.gateway_client import GatewayEmbedder
        embedder = GatewayEmbedder(s, s.embedding_model[len(GATEWAY_EMBEDDING_PREFIX):])
    try:
        return VectorStore(s.chroma_dir, s.chroma_collection, s.embedding_model, embedder=embedder)
    except ValueError as e:
        if "not supported" not in str(e):
            raise
        raise ConfigError(f"KM_EMBEDDING_MODEL={s.embedding_model} is not a local embedding model. "
                          f"{_EMBEDDING_HELP}") from e


def build_qa_service(s: Settings, llm: LLMClient | None = None) -> QAService:
    llm = llm or build_llm(s)
    sql_store = SqlStore(s.sqlite_path)
    vectors = build_vector_store(s)
    return QAService(
        router=IntentRouter(llm),
        docs=DocRetriever(vectors, s.top_k),
        sql=SqlRetriever(llm, sql_store, s.sql_max_rows),
        writer=AnswerWriter(llm),
        validator=GroundednessValidator(llm),
        sql_store=sql_store)


def build_indexer(s: Settings) -> Indexer:
    return Indexer(build_vector_store(s),
                   s.chunk_size, s.chunk_overlap, ocr=s.ocr_enabled, ocr_min_chars=s.ocr_min_chars)


def build_judge_llm(s: Settings) -> LLMClient:
    """The grading model for benchmarks. Use a different model than the one being tested
    (KM_JUDGE_PROVIDER / KM_JUDGE_MODEL), so the system does not grade its own homework."""
    if s.judge_provider is None and s.judge_model is None:
        return build_llm(s)
    provider = s.judge_provider or s.llm_provider
    update = {"llm_provider": provider}
    if s.judge_model:
        if provider == "gateway":  # the gateway picks the model by URL
            field = "gateway_chat_url" if s.judge_model.startswith("http") else "gateway_model"
        else:
            field = "grok_model" if provider == "grok_cli" else "llm_model"
        update[field] = s.judge_model
    return build_llm(s.model_copy(update=update))
