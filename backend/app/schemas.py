"""Request/response models for the HTTP API. Secrets never appear here except in
``GuessResponse.secret`` after a correct guess."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NewSessionRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=24)


class SessionResponse(BaseModel):
    session_id: str
    nickname: str
    provider: str


class ExplainerOut(BaseModel):
    defense: str
    how_it_works: str
    why_it_failed: str
    real_world: str
    stronger_fix: str


class LevelOut(BaseModel):
    id: int
    name: str
    guard_name: str
    tagline: str
    defenses: list[str]
    hint: str
    unlocked: bool
    solved: bool
    attempts: int
    guesses: int
    explainer: ExplainerOut | None = None  # only once solved


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    reply: str
    blocked: bool
    caught_by: str | None
    reason: str | None
    outcome: str
    techniques: list[str]
    attempts: int


class GuessRequest(BaseModel):
    password: str = Field(min_length=1, max_length=64)


class GuessResponse(BaseModel):
    correct: bool
    level: int
    guesses: int
    secret: str | None = None
    next_level: int | None = None
    explainer: ExplainerOut | None = None


class TranscriptItem(BaseModel):
    prompt: str
    response: str
    blocked: bool
    caught_by: str | None
    outcome: str
    techniques: list[str]
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str | None
