"""Composable guard pipeline.

A level is a stack of :class:`Defense` middlewares wrapped around a :class:`Responder`
(the thing that actually calls the model). Each middleware receives the request
context and ``call_next``; it may short-circuit (block input), mutate the context
(e.g. add system-prompt instructions) or inspect the response on the way back out
(block output). This is the same onion model as ASGI / Express middleware, which
keeps every layer independently testable.

    RateLimit -> InputFilter -> ... -> OutputFilter -> Responder(model)
                                   <- response flows back out <-
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

from app.providers.base import ChatMessage, ChatProvider

Stage = Literal["input", "prompt", "output", "model"]


@dataclass(slots=True)
class TraceEvent:
    layer: str
    action: Literal["pass", "block", "modify", "info"]
    detail: str = ""


@dataclass(slots=True)
class GuardContext:
    """Everything a defense needs to know about one chat turn."""

    level: int
    secret: str
    user_input: str
    provider: ChatProvider
    history: list[ChatMessage] = field(default_factory=list)
    system_prompt_parts: list[str] = field(default_factory=list)
    # The user message actually sent to the guard model (defenses may wrap/transform it).
    model_input: str = ""
    # Per (session, level) persistent state, e.g. rate-limit timestamps, leaked fragments.
    state: dict[str, Any] = field(default_factory=dict)
    now: float = field(default_factory=time.time)
    trace: list[TraceEvent] = field(default_factory=list)
    # Raw model output before output-side defenses ran (for research logging).
    raw_model_output: str | None = None

    def __post_init__(self) -> None:
        if not self.model_input:
            self.model_input = self.user_input

    @property
    def system_prompt(self) -> str:
        return "\n\n".join(self.system_prompt_parts)

    def log(
        self, layer: str, action: Literal["pass", "block", "modify", "info"], detail: str = ""
    ) -> None:
        self.trace.append(TraceEvent(layer, action, detail))


@dataclass(slots=True)
class GuardResult:
    text: str
    blocked: bool = False
    caught_by: str | None = None
    reason: str | None = None


Handler = Callable[[GuardContext], Awaitable[GuardResult]]


class Defense(ABC):
    """A single defensive layer."""

    #: Stable identifier stored in the attack log (``caught_by``).
    name: ClassVar[str]
    #: Human-readable label for the UI.
    label: ClassVar[str]
    stage: ClassVar[Stage]

    @abstractmethod
    async def __call__(self, ctx: GuardContext, call_next: Handler) -> GuardResult: ...

    def block(self, ctx: GuardContext, reason: str, message: str | None = None) -> GuardResult:
        ctx.log(self.name, "block", reason)
        return GuardResult(
            text=message or f"🛡️ Blocked by {self.label}.",
            blocked=True,
            caught_by=self.name,
            reason=reason,
        )


class Responder(ABC):
    """Terminal handler: produces the guard's reply (usually by calling a model)."""

    name: ClassVar[str]

    @abstractmethod
    async def __call__(self, ctx: GuardContext) -> GuardResult: ...


class Pipeline:
    """Runs ``defenses`` (outermost first) around ``responder``."""

    def __init__(self, defenses: Sequence[Defense], responder: Responder) -> None:
        self.defenses = tuple(defenses)
        self.responder = responder

    @property
    def layer_names(self) -> list[str]:
        return [d.name for d in self.defenses] + [self.responder.name]

    async def run(self, ctx: GuardContext) -> GuardResult:
        handler: Handler = self.responder.__call__
        for defense in reversed(self.defenses):
            handler = _bind(defense, handler)
        return await handler(ctx)


def _bind(defense: Defense, nxt: Handler) -> Handler:
    async def handler(ctx: GuardContext) -> GuardResult:
        return await defense(ctx, nxt)

    return handler
