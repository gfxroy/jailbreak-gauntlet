"""Provider interface shared by every model backend."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant"]

# Why a completion is being requested. Real providers may route purposes to different
# models (e.g. a cheaper judge); the mock provider uses it to pick a simulated behaviour.
Purpose = Literal["guard", "judge", "quarantine", "classifier"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str


@runtime_checkable
class ChatProvider(Protocol):
    """Minimal async chat-completion interface."""

    name: str

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        purpose: Purpose = "guard",
        json_mode: bool = False,
    ) -> str:
        """Return the assistant's reply text for ``messages``."""
        ...
