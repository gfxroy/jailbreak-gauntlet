"""OpenAI Chat Completions provider."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI

from app.providers.base import ChatMessage, Purpose


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        judge_model: str | None = None,
        base_url: str | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._client = client or AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._judge_model = judge_model or model

    def _model_for(self, purpose: Purpose) -> str:
        return self._judge_model if purpose in ("judge", "classifier") else self._model

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        purpose: Purpose = "guard",
        json_mode: bool = False,
    ) -> str:
        kwargs: dict[str, Any] = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = await self._client.chat.completions.create(
            model=self._model_for(purpose),
            messages=[{"role": m.role, "content": m.content} for m in messages],  # type: ignore[misc]
            max_completion_tokens=400,
            **kwargs,
        )
        return response.choices[0].message.content or ""
