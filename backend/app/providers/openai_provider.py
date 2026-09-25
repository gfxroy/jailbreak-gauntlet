"""Provider for OpenAI and any OpenAI-compatible Chat Completions endpoint."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, BadRequestError

from app.providers.base import ChatMessage, ProviderError, Purpose

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}
# Failures after which trying a *different* model makes sense: retired/unknown model
# (404), per-model quota (429) and overload (5xx).
FALLBACK_STATUS = {404, 429, 500, 502, 503, 504}
_RETRY_IN = re.compile(r"retry in ([\d.]+)\s*s", re.IGNORECASE)
_RETRY_DELAY = re.compile(r"retryDelay'?\"?\s*:\s*'?\"?([\d.]+)s")


def retry_after_seconds(exc: APIStatusError) -> float | None:
    """How long the server asked us to wait: Retry-After header or Gemini's RetryInfo."""
    header = exc.response.headers.get("retry-after") if exc.response is not None else None
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    text = f"{exc.message} {exc.body}"
    for pattern in (_RETRY_IN, _RETRY_DELAY):
        match = pattern.search(text)
        if match:
            return float(match.group(1))
    return None


def _rejects_reasoning_effort(exc: BadRequestError) -> bool:
    text = f"{exc.message} {exc.body}".lower()
    return "thinking" in text or "reasoning" in text or "invalid argument" in text


class OpenAIProvider:
    """Routes each purpose to its own model and copes with flaky / quota-limited backends.

    * transient errors (429/5xx/timeouts) are retried with exponential backoff, honouring
      the server's requested delay (Retry-After or Gemini's ``retryDelay``) up to
      ``max_retry_wait`` seconds; longer waits (e.g. an exhausted daily quota) fail fast;
    * if a model keeps failing, or is retired (404), the ``fallback_models`` are tried;
    * a model that rejects ``reasoning_effort`` (400) is retried once without it and
      remembered, so mixed model families work with a single setting;
    * an empty completion (a thinking model that spent its budget on reasoning) is retried.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        models: Mapping[Purpose, str | None] | None = None,
        fallback_models: Sequence[str] = (),
        base_url: str | None = None,
        client: AsyncOpenAI | None = None,
        max_tokens: int = 800,
        reasoning_effort: str | None = None,
        json_mode: bool = True,
        max_retries: int = 2,
        timeout: float = 45.0,
        backoff_seconds: float = 2.0,
        max_retry_wait: float = 20.0,
        attempts: int = 3,
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
        self._fallbacks = [m for m in fallback_models if m]
        self._retired: set[str] = set()  # models that returned 404; skipped from then on
        self._max_tokens = max_tokens
        self._reasoning_effort = reasoning_effort
        self._no_reasoning_effort: set[str] = set()
        self._json_mode = json_mode
        self._backoff = backoff_seconds
        self._max_retry_wait = max_retry_wait
        self._attempts = max(1, attempts)

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
        payload = [{"role": m.role, "content": m.content} for m in messages]
        primary = self.model_for(purpose)
        candidates = [primary] + [m for m in self._fallbacks if m != primary]
        candidates = [m for m in candidates if m not in self._retired] or candidates
        last: ProviderError | None = None
        for index, model in enumerate(candidates):
            try:
                return await self._complete_with(model, payload, purpose, json_mode)
            except ProviderError as exc:
                last = exc
                status = getattr(exc.__cause__, "status_code", None)
                if status == 404 and index < len(candidates) - 1:
                    self._retired.add(model)
                if status not in FALLBACK_STATUS or index == len(candidates) - 1:
                    raise
                log.warning("%s failed (%s); falling back to %s", model, exc, candidates[index + 1])
        raise last or ProviderError("no model available")  # pragma: no cover

    def _kwargs(self, model: str, json_mode: bool) -> dict[str, Any]:
        # OpenAI's newer models require `max_completion_tokens`; most compatible
        # endpoints (Gemini, vLLM, Ollama) still expect `max_tokens`.
        token_param = "max_completion_tokens" if self.name == "openai" else "max_tokens"
        kwargs: dict[str, Any] = {token_param: self._max_tokens}
        if json_mode and self._json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if self._reasoning_effort and model not in self._no_reasoning_effort:
            kwargs["reasoning_effort"] = self._reasoning_effort
        return kwargs

    async def _complete_with(
        self, model: str, payload: list[dict[str, str]], purpose: Purpose, json_mode: bool
    ) -> str:
        attempt = 0
        while True:
            attempt += 1
            kwargs = self._kwargs(model, json_mode)
            wait = self._backoff * 2 ** (attempt - 1)
            try:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=payload,  # type: ignore[arg-type]
                    **kwargs,
                )
            except BadRequestError as exc:
                if "reasoning_effort" in kwargs and _rejects_reasoning_effort(exc):
                    log.info("%s rejected reasoning_effort; retrying without it", model)
                    self._no_reasoning_effort.add(model)
                    attempt -= 1
                    continue
                raise ProviderError(f"HTTP 400 from {model}") from exc
            except APIConnectionError as exc:
                if attempt >= self._attempts:
                    raise ProviderError(f"{type(exc).__name__} from {model}") from exc
            except APIStatusError as exc:
                if exc.status_code not in RETRYABLE_STATUS or attempt >= self._attempts:
                    raise ProviderError(f"HTTP {exc.status_code} from {model}") from exc
                requested = retry_after_seconds(exc)
                if requested is not None:
                    if requested > self._max_retry_wait:
                        raise ProviderError(
                            f"HTTP {exc.status_code} from {model} (retry in {requested:.0f}s)"
                        ) from exc
                    wait = max(wait, requested)
            else:
                content = response.choices[0].message.content if response.choices else None
                if content and content.strip():
                    return content
                if attempt >= self._attempts:
                    return ""
                log.warning("empty completion from %s (%s), retrying", model, purpose)
            await asyncio.sleep(wait)
