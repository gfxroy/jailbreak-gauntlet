"""Database tables (SQLModel on SQLite by default)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class Outcome(StrEnum):
    LEAKED = "leaked"  # reply delivered and contained the secret (any variant)
    PARTIAL_LEAK = "partial_leak"  # reply delivered with fragments or hints
    REFUSED = "refused"  # model answered without disclosing anything
    BLOCKED = "blocked"  # a defense layer intercepted the input or output
    RATE_LIMITED = "rate_limited"


class GameSession(SQLModel, table=True):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    nickname: str = Field(max_length=24, index=True)
    # level -> secret word. Server-side only; never serialized to clients.
    secrets: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    synthetic: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow)


class LevelProgress(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("session_id", "level"),)

    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="gamesession.id", index=True)
    level: int = Field(index=True)
    attempts: int = 0
    guesses: int = 0
    solved: bool = False
    solved_at: datetime | None = None
    # Pipeline state (rate-limit timestamps, leaked positions, canary token...).
    state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class Attempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="gamesession.id", index=True)
    level: int = Field(index=True)
    prompt: str
    response: str
    outcome: Outcome = Field(index=True)
    caught_by: str | None = Field(default=None, index=True)
    block_reason: str | None = None
    # Did the raw model output contain the secret, even if a defense then blocked it?
    model_leaked: bool = False
    techniques: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    provider: str = "mock"
    latency_ms: int = 0
    synthetic: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
