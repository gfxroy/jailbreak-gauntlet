"""Abuse and cost controls for public deployments.

Three independent budgets, all in memory (a single-process demo; see README):

* per visitor (client IP): chat messages per window, and model calls per window -
  every guard, judge, quarantine and labeler call counts;
* global: model calls per UTC day, so a public demo can't exhaust the API key;
* per visitor: new sessions per hour, so nobody floods the database.

Model calls are metered by wrapping the provider (:class:`MeteredProvider`); the
visitor for the current request is carried in a ``ContextVar``.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.providers.base import ChatMessage, ChatProvider, Purpose

current_client: ContextVar[str] = ContextVar("current_client", default="local")


class QuotaExceeded(Exception):
    """A usage budget is exhausted. ``message`` is safe to show to the visitor."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


@dataclass
class SlidingWindow:
    limit: int
    window_seconds: float
    _hits: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def _prune(self, key: str, now: float) -> deque[float]:
        hits = self._hits[key]
        while hits and hits[0] <= now - self.window_seconds:
            hits.popleft()
        return hits

    def remaining(self, key: str, now: float) -> int:
        return max(0, self.limit - len(self._prune(key, now)))

    def retry_after(self, key: str, now: float) -> int:
        hits = self._prune(key, now)
        return int(hits[0] + self.window_seconds - now) + 1 if hits else 0

    def add(self, key: str, now: float, n: int = 1) -> None:
        self._prune(key, now).extend([now] * n)


@dataclass
class LimitConfig:
    enabled: bool
    visitor_messages: int = 15
    visitor_model_calls: int = 60
    visitor_window_seconds: float = 600
    visitor_sessions_per_hour: int = 10
    global_daily_model_calls: int = 2000


class UsageLimiter:
    def __init__(self, config: LimitConfig) -> None:
        self.config = config
        self._clock = time.time
        self.messages = SlidingWindow(config.visitor_messages, config.visitor_window_seconds)
        self.model_calls = SlidingWindow(config.visitor_model_calls, config.visitor_window_seconds)
        self.sessions = SlidingWindow(config.visitor_sessions_per_hour, 3600)
        self._day = ""
        self._day_calls = 0

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def now(self) -> float:
        return self._clock()

    def _roll_day(self, now: float) -> None:
        day = datetime.fromtimestamp(now, UTC).date().isoformat()
        if day != self._day:
            self._day, self._day_calls = day, 0

    @staticmethod
    def _minutes(seconds: int) -> str:
        return f"{max(1, round(seconds / 60))} min" if seconds >= 60 else f"{seconds}s"

    def _check_global(self, now: float, needed: int) -> None:
        self._roll_day(now)
        if self._day_calls + needed > self.config.global_daily_model_calls:
            raise QuotaExceeded(
                "This public demo has used up today's model budget. It resets at 00:00 UTC. "
                "You can also run the game locally with your own key (or none, in demo mode)."
            )

    def check_message(self, visitor: str, expected_model_calls: int) -> None:
        """Called once per chat message, before any model call."""
        if not self.enabled:
            return
        now = self.now()
        if self.messages.remaining(visitor, now) < 1:
            wait = self.messages.retry_after(visitor, now)
            raise QuotaExceeded(
                f"Easy there! This demo allows {self.config.visitor_messages} messages per "
                f"{self._minutes(int(self.config.visitor_window_seconds))} per visitor. "
                f"Try again in {self._minutes(wait)}.",
                retry_after=wait,
            )
        if self.model_calls.remaining(visitor, now) < expected_model_calls:
            wait = self.model_calls.retry_after(visitor, now)
            raise QuotaExceeded(
                "You've hit this demo's per-visitor model budget (the judge and parser "
                f"models count too). Try again in {self._minutes(wait)}.",
                retry_after=wait,
            )
        self._check_global(now, expected_model_calls)
        self.messages.add(visitor, now)

    def charge_model_call(self, visitor: str) -> None:
        if not self.enabled:
            return
        now = self.now()
        if self.model_calls.remaining(visitor, now) < 1:
            raise QuotaExceeded(
                "Per-visitor model budget reached mid-turn. Try again in "
                f"{self._minutes(self.model_calls.retry_after(visitor, now))}.",
                retry_after=self.model_calls.retry_after(visitor, now),
            )
        self._check_global(now, 1)
        self.model_calls.add(visitor, now)
        self._day_calls += 1

    def check_new_session(self, visitor: str) -> None:
        if not self.enabled:
            return
        now = self.now()
        if self.sessions.remaining(visitor, now) < 1:
            raise QuotaExceeded(
                "Too many new games from your network. Try again later.",
                retry_after=self.sessions.retry_after(visitor, now),
            )
        self.sessions.add(visitor, now)

    @property
    def daily_calls_used(self) -> int:
        self._roll_day(self.now())
        return self._day_calls


class MeteredProvider:
    """Wraps a provider so every model call is charged to the current visitor."""

    def __init__(self, inner: ChatProvider, limiter: UsageLimiter) -> None:
        self.inner = inner
        self.limiter = limiter
        self.name: str = inner.name
        self.model: str | None = getattr(inner, "model", None)

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        purpose: Purpose = "guard",
        json_mode: bool = False,
    ) -> str:
        self.limiter.charge_model_call(current_client.get())
        return await self.inner.complete(messages, purpose=purpose, json_mode=json_mode)
