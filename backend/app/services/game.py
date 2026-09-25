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
from app.defenses.llm_judge import LLMJudge
from app.defenses.prompts import base_prompt
from app.defenses.responders import DualLLMResponder
from app.levels import MAX_LEVEL, LevelSpec, get_level
from app.limits import LimitConfig, MeteredProvider, QuotaExceeded, UsageLimiter, current_client
from app.models import Attempt, GameSession, LevelProgress, Outcome, utcnow
from app.providers.base import ChatMessage, ChatProvider, ProviderError
from app.wordbank import draw_secrets, lookup

HISTORY_TURNS = 6


def _ts(now: float | None) -> datetime:
    if now is None:
        return utcnow()
    return datetime.fromtimestamp(now, UTC)


class GameError(Exception):
    status_code = 400

    def __init__(self, message: str, *, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class NotFound(GameError):
    status_code = 404


class LevelLocked(GameError):
    status_code = 403


class TooManyRequests(GameError):
    status_code = 429


class ProviderUnavailable(GameError):
    status_code = 503


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
    def __init__(
        self,
        engine: Engine,
        provider: ChatProvider,
        settings: Settings,
        limiter: UsageLimiter | None = None,
    ) -> None:
        self.engine = engine
        self.settings = settings
        self.limiter = limiter or UsageLimiter(
            LimitConfig(
                enabled=settings.limits_enabled,
                visitor_messages=settings.visitor_max_messages,
                visitor_model_calls=settings.visitor_max_model_calls,
                visitor_window_seconds=settings.visitor_window_seconds,
                visitor_sessions_per_hour=settings.visitor_sessions_per_hour,
                global_daily_model_calls=settings.global_daily_model_calls,
            )
        )
        # Every model call (guard, judge, parser, labeler) is charged to the visitor.
        self.provider: ChatProvider = MeteredProvider(provider, self.limiter)
        self.throttle = SessionThrottle()

    def expected_model_calls(self, spec: LevelSpec) -> int:
        defenses, responder = spec.build(self.settings)
        calls = 2 if isinstance(responder, DualLLMResponder) else 1
        calls += sum(isinstance(d, LLMJudge) for d in defenses)
        return calls + (1 if self.settings.classifier_use_llm else 0)

    @property
    def provider_label(self) -> str:
        model = getattr(self.provider, "model", None)
        return f"{self.provider.name}:{model}" if model else self.provider.name

    # ---------------------------------------------------------------- sessions
    def create_session(
        self, nickname: str, *, synthetic: bool = False, client_ip: str = "local"
    ) -> GameSession:
        try:
            self.limiter.check_new_session(client_ip)
        except QuotaExceeded as exc:
            raise TooManyRequests(exc.message, retry_after=exc.retry_after) from None
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
        self,
        session_id: str,
        level_id: int,
        message: str,
        *,
        now: float | None = None,
        client_ip: str = "local",
    ) -> ChatOutcome:
        """Run one chat turn through the level's defense pipeline and log it.

        ``now`` (epoch seconds) is only overridden by the synthetic-data seeder.
        """
        try:
            spec = get_level(level_id)
        except KeyError as exc:
            raise NotFound(str(exc)) from None
        if len(message) > self.settings.max_input_chars:
            raise GameError(f"message too long (max {self.settings.max_input_chars} characters)")
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
        token = current_client.set(client_ip)
        try:
            self.limiter.check_message(client_ip, self.expected_model_calls(spec))
            started = time.perf_counter()
            result = await spec.pipeline(self.settings).run(ctx)
            latency = int((time.perf_counter() - started) * 1000)
            techniques = [
                t.value
                for t in await classify(
                    message, self.provider, use_llm=self.settings.classifier_use_llm
                )
            ]
        except QuotaExceeded as exc:
            raise TooManyRequests(exc.message, retry_after=exc.retry_after) from None
        except ProviderError as exc:
            # Nothing is logged: a failed backend call is not an attempt.
            raise ProviderUnavailable(
                "the model provider is unavailable right now; please try again shortly"
            ) from exc
        finally:
            current_client.reset(token)

        outcome = label_outcome(result, secret)
        raw = ctx.raw_model_output or ""
        raw_report = SecretDetector(secret).scan(raw)

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
                    provider=self.provider_label,
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
