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
    #   grok_cli  = the local Grok CLI, used to simulate the gateway during development
    llm_provider: Literal["anthropic", "grok_cli"] = "anthropic"

    # Company LLM gateway (KM_LLM_*): put your token in .env, never in code
    llm_api_token: SecretStr | None = None
    llm_base_url: str | None = None
    llm_auth_mode: Literal["api_key", "bearer"] = "api_key"
    llm_model: str = "claude-opus-5-5"
    llm_server_fallbacks: bool = True
    llm_timeout_s: float = 60.0
    llm_max_retries: int = 2

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
