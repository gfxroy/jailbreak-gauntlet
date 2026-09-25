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
            models={
                "judge": settings.openai_judge_model,
                "quarantine": settings.openai_quarantine_model,
                "classifier": settings.openai_labeler_model,
            },
            base_url=settings.openai_base_url,
            max_tokens=settings.openai_max_tokens,
            reasoning_effort=settings.openai_reasoning_effort,
            json_mode=settings.openai_json_mode,
            max_retries=settings.openai_max_retries,
            timeout=settings.openai_timeout_seconds,
        )
    return MockProvider()
