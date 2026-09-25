"""Application settings, loaded from environment variables / `.env`."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # "auto" uses OpenAI when OPENAI_API_KEY is set and falls back to the offline mock.
    provider: Literal["auto", "openai", "mock"] = "auto"
    # Any OpenAI-compatible Chat Completions endpoint works (OpenAI, Gemini, a local
    # vLLM/Ollama server, ...): set OPENAI_BASE_URL and the model names.
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4.1-mini"  # guard (privileged) model
    openai_judge_model: str | None = None  # defaults to openai_model
    openai_quarantine_model: str | None = None  # dual-LLM parser; defaults to openai_model
    openai_labeler_model: str | None = None  # technique labeler; defaults to judge model
    openai_max_tokens: int = 800
    # Forwarded as `reasoning_effort` when set (e.g. "none"/"low" to keep thinking models
    # such as gemini-2.5-flash from spending the whole token budget on reasoning).
    openai_reasoning_effort: str | None = None
    # Ask for JSON mode on judge/parser/labeler calls. Disable for endpoints without it.
    openai_json_mode: bool = True
    openai_max_retries: int = 2  # SDK-level retries (our own retry loop sits on top)
    openai_fallback_models: str | None = None  # comma-separated, tried when a model fails
    openai_max_retry_wait: float = 20.0  # longest server-requested wait we honour per retry
    openai_timeout_seconds: float = 45.0

    # "production" hardens the app for a public demo (see README > Deploying).
    app_env: Literal["development", "production"] = "development"
    # Unset = ./gauntlet.db in development; in production /data (persistent storage on
    # e.g. Hugging Face Spaces) if writable, else /tmp (ephemeral, fine for a demo).
    database_url: str | None = None
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Serve the built frontend from FastAPI (single-container deployments).
    static_dir: str | None = None
    enable_docs: bool | None = None  # default: on in development, off in production
    # Admin endpoints (seed / wipe synthetic data). Never available in production.
    enable_admin: bool = False
    # Seed the synthetic sample dataset at startup if the database has none (mock only,
    # no API cost). Handy for ephemeral demo hosting.
    seed_on_startup: bool = False
    seed_players: int = 60

    # Hard server-side cap on player message length.
    max_input_chars: int = 1000

    # Per-visitor and global usage limits. "auto" = on whenever a real model is used.
    usage_limits: Literal["auto", "on", "off"] = "auto"
    visitor_max_messages: int = 15
    visitor_max_model_calls: int = 60  # guard + judge + parser + labeler calls
    visitor_window_seconds: float = 600
    visitor_sessions_per_hour: int = 10
    global_daily_model_calls: int = 2000
    # Number of reverse proxies in front of the app whose X-Forwarded-For entries are
    # trusted (1 on Hugging Face Spaces). 0 = use the socket peer address.
    trusted_proxy_hops: int = 0

    # Use an LLM (in addition to heuristics) to label attack techniques.
    classifier_use_llm: bool = False

    # Defense-in-depth level rate limit.
    rate_limit_max_requests: int = 6
    rate_limit_window_seconds: float = 60.0

    @field_validator(
        "openai_api_key",
        "openai_base_url",
        "openai_judge_model",
        "openai_quarantine_model",
        "openai_labeler_model",
        "openai_reasoning_effort",
        "openai_fallback_models",
        "database_url",
        "static_dir",
        mode="before",
    )
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        # `.env` lines like `OPENAI_BASE_URL=` mean "unset", not "empty string".
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def docs_enabled(self) -> bool:
        return self.enable_docs if self.enable_docs is not None else not self.is_production

    @property
    def admin_enabled(self) -> bool:
        return self.enable_admin and not self.is_production

    @property
    def limits_enabled(self) -> bool:
        if self.usage_limits == "auto":
            return self.resolved_provider != "mock"
        return self.usage_limits == "on"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        if not self.is_production:
            return "sqlite:///./gauntlet.db"
        for directory in ("/data", "/tmp"):
            if os.path.isdir(directory) and os.access(directory, os.W_OK):
                return f"sqlite:///{directory}/gauntlet.db"
        return "sqlite:///./gauntlet.db"

    @property
    def resolved_provider(self) -> Literal["openai", "mock"]:
        if self.provider == "auto":
            return "openai" if self.openai_api_key else "mock"
        return self.provider


@lru_cache
def get_settings() -> Settings:
    return Settings()
