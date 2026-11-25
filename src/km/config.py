"""Typed settings. This is the only module that reads environment variables / .env
(observability.py additionally lets the Langfuse SDK read its own LANGFUSE_* variables)."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="KM_", extra="ignore")

    # Which LLM backend to use:
    #   anthropic = the company LLM gateway (production)
    #   gateway   = the company AI gateway's OpenAI-style chat/completions endpoint (KM_GATEWAY_*)
    #   grok_cli  = the local Grok CLI, used to simulate the gateway during development
    llm_provider: Literal["anthropic", "gateway", "grok_cli"] = "anthropic"

    # Company LLM gateway (KM_LLM_*): put your token in .env, never in code
    llm_api_token: SecretStr | None = None
    llm_base_url: str | None = None
    llm_auth_mode: Literal["api_key", "bearer"] = "api_key"
    llm_model: str = "claude-opus-5-5"
    llm_server_fallbacks: bool = True
    llm_timeout_s: float = 60.0
    llm_max_retries: int = 2

    # Company AI gateway, OpenAI-compatible (KM_GATEWAY_*). The full URLs come from the gateway guide:
    #   .../<Use Case ID>/<Model Provider>/<Model Name>/chat/completions   and   .../embeddings
    gateway_chat_url: str | None = None
    gateway_embed_url: str | None = None
    gateway_token: SecretStr | None = None   # staff AM token or service-account JWT
    gateway_auth: Literal["staff", "service"] = "staff"   # staff adds Token_Type: SESSION_TOKEN
    gateway_model: str | None = None         # sent as "model" in the body only when set
    # How to get JSON for structured outputs: prompt = schema in the prompt (works everywhere);
    # json_object / json_schema = also send response_format, if the gateway's model supports it
    gateway_json_mode: Literal["prompt", "json_object", "json_schema"] = "prompt"
    gateway_max_tokens: int | None = None
    gateway_timeout_s: float = 120.0
    gateway_max_retries: int = 2
    gateway_embed_batch: int = 32            # texts per embeddings request
    gateway_use_truststore: bool = True      # trust the OS certificate store (corporate root CA)

    # Grok CLI simulator (KM_GROK_*)
    grok_bin: str = "grok"
    grok_model: str | None = None          # None = the CLI's default model
    grok_effort: str | None = None         # low | medium | high; None = the CLI's default
    grok_timeout_s: float = 180.0

    # Storage
    docs_dir: Path = Path("data/raw/docs")
    seed_sql: Path = Path("data/seed/seed.sql")
    sqlite_path: Path = Path("data/sqlite/km.db")
    chroma_dir: Path = Path("data/chroma")
    chroma_collection: str = "docs"

    # Retrieval
    chunk_size: int = 800
    chunk_overlap: int = 150
    top_k: int = 4
    sql_max_rows: int = 50
    # "default" = Chroma's built-in English model (all-MiniLM-L6-v2).
    # Any fastembed model name switches models, e.g. a multilingual one:
    #   sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
    # gateway:<model name> = the company AI gateway's embeddings endpoint (KM_GATEWAY_EMBED_URL).
    # Changing it requires re-indexing (km ingest); each model gets its own collection.
    embedding_model: str = "default"

    # Ingestion
    ocr_enabled: bool = True        # OCR pages that have no text layer (scanned PDFs)
    ocr_min_chars: int = 20         # a page with fewer extracted characters is treated as scanned

    # Evaluation: grade answers with a different model than the one being tested
    judge_provider: Literal["anthropic", "gateway", "grok_cli"] | None = None   # None = same as llm_provider
    judge_model: str | None = None   # for the gateway, a full chat/completions URL selects another model

    # Question log (feeds the benchmark dataset). Off unless a path is set.
    # Logs contain user questions: treat the file as Internal data.
    question_log: Path | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
