"""Provider for OpenAI and any OpenAI-compatible Chat Completions endpoint."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from app.providers.base import ChatMessage, ProviderError, Purpose

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class OpenAIProvider:
    """Routes each purpose to its own model and retries transient failures.

    The SDK already retries 429/5xx with exponential backoff (``max_retries``); on top of
    that we retry a couple of times with our own backoff, which covers free-tier quota
    bursts, and treat an empty completion (e.g. a thinking model that spent its whole
    budget on reasoning) as retryable once.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        models: Mapping[Purpose, str | None] | None = None,
        base_url: str | None = None,
        client: AsyncOpenAI | None = None,
        max_tokens: int = 800,
        reasoning_effort: str | None = None,
        json_mode: bool = True,
        max_retries: int = 4,
        timeout: float = 45.0,
        backoff_seconds: float = 2.0,
    ) -> None:
        self._client = client or AsyncOpenAI(
            api_key=api_key, base_url=base_url, max_retries=max_retries, timeout=timeout
        )
        self.name = (
            "openai" if not base_url or "api.openai.com" in base_url else "openai-compatible"
        )
        self.model = model
        self._models: dict[str, str] = {"guard": model}
        for purpose, name in (models or {}).items():
            if name:
                self._models[purpose] = name
        self._max_tokens = max_tokens
        self._reasoning_effort = reasoning_effort
        self._json_mode = json_mode
        self._backoff = backoff_seconds

    def model_for(self, purpose: Purpose) -> str:
        if purpose == "classifier":
            return self._models.get("classifier") or self._models.get("judge") or self.model
        return self._models.get(purpose, self.model)

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        purpose: Purpose = "guard",
        json_mode: bool = False,
    ) -> str:
        # OpenAI's newer models require `max_completion_tokens`; most compatible
        # endpoints (Gemini, vLLM, Ollama) still expect `max_tokens`.
        token_param = "max_completion_tokens" if self.name == "openai" else "max_tokens"
        kwargs: dict[str, Any] = {token_param: self._max_tokens}
        if json_mode and self._json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if self._reasoning_effort:
            kwargs["reasoning_effort"] = self._reasoning_effort
        payload = [{"role": m.role, "content": m.content} for m in messages]
        model = self.model_for(purpose)

        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=payload,  # type: ignore[arg-type]
                    **kwargs,
                )
            except (RateLimitError, APIConnectionError) as exc:
                if attempt == attempts:
                    raise ProviderError(f"{type(exc).__name__} from {model}") from exc
            except APIStatusError as exc:
                if exc.status_code not in RETRYABLE_STATUS or attempt == attempts:
                    raise ProviderError(f"HTTP {exc.status_code} from {model}") from exc
            else:
                content = response.choices[0].message.content if response.choices else None
                if content and content.strip():
                    return content
                if attempt == attempts:
                    return ""
                log.warning("empty completion from %s (%s), retrying", model, purpose)
            await asyncio.sleep(self._backoff * 2 ** (attempt - 1))
        return ""  # pragma: no cover
