"""Game orchestration: sessions, chat turns, guesses and attack logging."""

from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.classifier import classify
from app.config import Settings
from app.defenses.base import GuardContext, GuardResult
from app.defenses.leak_detection import SecretDetector
from app.defenses.prompts import base_prompt
from app.levels import MAX_LEVEL, LevelSpec, get_level
from app.models import Attempt, GameSession, LevelProgress, Outcome, utcnow
from app.providers.base import ChatMessage, ChatProvider
from app.wordbank import draw_secrets, lookup

HISTORY_TURNS = 6


def _ts(now: float | None) -> datetime:
    if now is None:
        return utcnow()
    return datetime.fromtimestamp(now, UTC)


class GameError(Exception):
    status_code = 400


class NotFound(GameError):
    status_code = 404


class LevelLocked(GameError):
    status_code = 403


class TooManyRequests(GameError):
    status_code = 429


@dataclass(slots=True)
class ChatOutcome:
    reply: str
    blocked: bool
    caught_by: str | None
    reason: str | None
    outcome: Outcome
    techniques: list[str]
    attempts: int


@dataclass(slots=True)
class GuessOutcome:
    correct: bool
    level: int
    secret: str | None = None
    next_level: int | None = None
    guesses: int = 0


@dataclass(slots=True)
class LevelStatus:
    spec: LevelSpec
    unlocked: bool
    solved: bool
    attempts: int
    guesses: int


def label_outcome(result: GuardResult, secret: str) -> Outcome:
    """Classify what the *player actually received*."""
    if result.blocked:
        return Outcome.RATE_LIMITED if result.caught_by == "rate_limit" else Outcome.BLOCKED
    report = SecretDetector(secret).scan(result.text)
    if report.full_leak or report.acrostic:
        return Outcome.LEAKED
    info = lookup(secret)
    hinted = info is not None and (
        info.rhyme.lower() in result.text.lower() or info.description.lower() in result.text.lower()
    )
    if report.fragments or SecretDetector.positional_letters(secret, result.text) or hinted:
        return Outcome.PARTIAL_LEAK
    return Outcome.REFUSED


@dataclass
class SessionThrottle:
    """Process-wide safety net against runaway API spend (independent of level 8)."""

    max_requests: int = 30
    window_seconds: float = 60.0
    _hits: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        hits = self._hits[key]
        while hits and hits[0] <= now - self.window_seconds:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True


class GameService:
    def __init__(self, engine: Engine, provider: ChatProvider, settings: Settings) -> None:
        self.engine = engine
        self.provider = provider
        self.settings = settings
        self.throttle = SessionThrottle()

    # ---------------------------------------------------------------- sessions
    def create_session(self, nickname: str, *, synthetic: bool = False) -> GameSession:
        clean = re.sub(r"[^\w\- .]", "", nickname).strip()[:24] or "anonymous"
        game = GameSession(
            nickname=clean,
            secrets={str(k): v for k, v in draw_secrets(MAX_LEVEL).items()},
            synthetic=synthetic,
        )
        with Session(self.engine) as db:
            db.add(game)
            db.commit()
            db.refresh(game)
        return game

    def get_session(self, db: Session, session_id: str) -> GameSession:
        game = db.get(GameSession, session_id)
        if game is None:
            raise NotFound("session not found - start a new game")
        return game

    @staticmethod
    def _progress(db: Session, session_id: str, level: int) -> LevelProgress:
        progress = db.exec(
            select(LevelProgress).where(
                LevelProgress.session_id == session_id, LevelProgress.level == level
            )
        ).first()
        if progress is None:
            progress = LevelProgress(session_id=session_id, level=level)
            db.add(progress)
        return progress

    def level_statuses(self, session_id: str | None) -> list[LevelStatus]:
        from app.levels import LEVELS

        solved: dict[int, LevelProgress] = {}
        if session_id:
            with Session(self.engine) as db:
                rows = db.exec(
                    select(LevelProgress).where(LevelProgress.session_id == session_id)
                ).all()
                solved = {p.level: p for p in rows}
        statuses = []
        for spec in LEVELS:
            p = solved.get(spec.id)
            prev = solved.get(spec.id - 1)
            unlocked = spec.id == 1 or bool(prev and prev.solved)
            statuses.append(
                LevelStatus(
                    spec=spec,
                    unlocked=unlocked and session_id is not None,
                    solved=bool(p and p.solved),
                    attempts=p.attempts if p else 0,
                    guesses=p.guesses if p else 0,
                )
            )
        return statuses

    def _ensure_unlocked(self, db: Session, session_id: str, level: int) -> None:
        if level == 1:
            return
        prev = self._progress(db, session_id, level - 1)
        if not prev.solved:
            raise LevelLocked(f"level {level} is locked - solve level {level - 1} first")

    # -------------------------------------------------------------------- chat
    async def chat(
        self, session_id: str, level_id: int, message: str, *, now: float | None = None
    ) -> ChatOutcome:
        """Run one chat turn through the level's defense pipeline and log it.

        ``now`` (epoch seconds) is only overridden by the synthetic-data seeder.
        """
        try:
            spec = get_level(level_id)
        except KeyError as exc:
            raise NotFound(str(exc)) from None
        if not self.throttle.allow(session_id, now):
            raise TooManyRequests("too many requests - slow down")

        with Session(self.engine) as db:
            game = self.get_session(db, session_id)
            self._ensure_unlocked(db, session_id, level_id)
            progress = self._progress(db, session_id, level_id)
            secret = game.secrets[str(level_id)]
            history = self._history(db, session_id, level_id)
            state = dict(progress.state)
            game_synthetic = game.synthetic

        ctx = GuardContext(
            level=level_id,
            secret=secret,
            user_input=message,
            provider=self.provider,
            history=history,
            system_prompt_parts=[base_prompt(spec.guard_name, secret)],
            state=state,
            now=time.time() if now is None else now,
        )
        started = time.perf_counter()
        result = await spec.pipeline(self.settings).run(ctx)
        latency = int((time.perf_counter() - started) * 1000)

        outcome = label_outcome(result, secret)
        raw = ctx.raw_model_output or ""
        raw_report = SecretDetector(secret).scan(raw)
        techniques = [
            t.value
            for t in await classify(
                message, self.provider, use_llm=self.settings.classifier_use_llm
            )
        ]

        with Session(self.engine) as db:
            progress = self._progress(db, session_id, level_id)
            progress.attempts += 1
            progress.state = ctx.state
            db.add(
                Attempt(
                    session_id=session_id,
                    level=level_id,
                    prompt=message,
                    response=result.text,
                    outcome=outcome,
                    caught_by=result.caught_by,
                    block_reason=result.reason,
                    model_leaked=raw_report.full_leak or raw_report.acrostic,
                    techniques=techniques,
                    provider=self.provider.name,
                    latency_ms=latency,
                    synthetic=game_synthetic,
                    created_at=_ts(now),
                )
            )
            db.add(progress)
            db.commit()
            attempts = progress.attempts

        return ChatOutcome(
            reply=result.text,
            blocked=result.blocked,
            caught_by=result.caught_by,
            reason=result.reason,
            outcome=outcome,
            techniques=techniques,
            attempts=attempts,
        )

    @staticmethod
    def _history(db: Session, session_id: str, level: int) -> list[ChatMessage]:
        rows = db.exec(
            select(Attempt)
            .where(Attempt.session_id == session_id, Attempt.level == level)
            .where(col(Attempt.outcome).not_in([Outcome.BLOCKED, Outcome.RATE_LIMITED]))
            .order_by(col(Attempt.id).desc())
            .limit(HISTORY_TURNS)
        ).all()
        messages: list[ChatMessage] = []
        for row in reversed(rows):
            messages += [ChatMessage("user", row.prompt), ChatMessage("assistant", row.response)]
        return messages

    def transcript(self, session_id: str, level: int) -> list[Attempt]:
        with Session(self.engine) as db:
            self.get_session(db, session_id)
            return list(
                db.exec(
                    select(Attempt)
                    .where(Attempt.session_id == session_id, Attempt.level == level)
                    .order_by(col(Attempt.id))
                ).all()
            )

    # ------------------------------------------------------------------- guess
    def guess(
        self, session_id: str, level_id: int, password: str, *, now: float | None = None
    ) -> GuessOutcome:
        try:
            get_level(level_id)
        except KeyError as exc:
            raise NotFound(str(exc)) from None
        with Session(self.engine) as db:
            game = self.get_session(db, session_id)
            self._ensure_unlocked(db, session_id, level_id)
            progress = self._progress(db, session_id, level_id)
            secret = game.secrets[str(level_id)]
            progress.guesses += 1
            correct = re.sub(r"[^A-Za-z]", "", password).upper() == secret
            if correct and not progress.solved:
                progress.solved = True
                progress.solved_at = _ts(now)
            db.add(progress)
            db.commit()
            return GuessOutcome(
                correct=correct,
                level=level_id,
                secret=secret if correct else None,
                next_level=level_id + 1 if correct and level_id < MAX_LEVEL else None,
                guesses=progress.guesses,
            )
