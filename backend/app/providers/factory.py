"""Build the configured provider."""

from __future__ import annotations

from app.config import Settings
from app.providers.base import ChatProvider
from app.providers.mock_provider import MockProvider


def build_provider(settings: Settings) -> ChatProvider:
    if settings.resolved_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("PROVIDER=openai requires OPENAI_API_KEY to be set")
        from app.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(
            settings.openai_api_key,
            settings.openai_model,
            judge_model=settings.openai_judge_model,
            base_url=settings.openai_base_url,
        )
    return MockProvider()
