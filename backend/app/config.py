"""Application settings, loaded from environment variables / `.env`."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # "auto" uses OpenAI when OPENAI_API_KEY is set and falls back to the offline mock.
    provider: Literal["auto", "openai", "mock"] = "auto"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_judge_model: str | None = None
    openai_base_url: str | None = None

    database_url: str = "sqlite:///./gauntlet.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Use an LLM (in addition to heuristics) to label attack techniques.
    classifier_use_llm: bool = False

    # Defense-in-depth level rate limit.
    rate_limit_max_requests: int = 6
    rate_limit_window_seconds: float = 60.0

    @property
    def resolved_provider(self) -> Literal["openai", "mock"]:
        if self.provider == "auto":
            return "openai" if self.openai_api_key else "mock"
        return self.provider


@lru_cache
def get_settings() -> Settings:
    return Settings()
