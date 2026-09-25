"""HTTP routes."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.levels import get_level
from app.schemas import (
    ChatRequest,
    ChatResponse,
    ExplainerOut,
    GuessRequest,
    GuessResponse,
    HealthResponse,
    LevelOut,
    NewSessionRequest,
    SessionResponse,
    TranscriptItem,
)
from app.services import research
from app.services.game import GameError, GameService

router = APIRouter(prefix="/api")

SessionHeader = Annotated[str, Header(alias="X-Session-Id", min_length=8, max_length=64)]
OptionalSession = Annotated[str | None, Header(alias="X-Session-Id")]
IncludeSynthetic = Annotated[bool, Query()]


def get_game(request: Request) -> GameService:
    service: GameService = request.app.state.game
    return service


Game = Annotated[GameService, Depends(get_game)]


def _raise(exc: GameError) -> HTTPException:
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
    return HTTPException(status_code=exc.status_code, detail=str(exc), headers=headers)


def client_ip(request: Request) -> str:
    """Visitor identity for rate limiting.

    Behind N trusted reverse proxies, the client is the N-th entry from the right of
    X-Forwarded-For (entries further left are client-controlled and spoofable).
    """
    hops: int = request.app.state.game.settings.trusted_proxy_hops
    if hops > 0:
        forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",")]
        forwarded = [p for p in forwarded if p]
        if len(forwarded) >= hops:
            return str(forwarded[-hops])
    return request.client.host if request.client else "unknown"


@router.get("/health", response_model=HealthResponse)
def health(game: Game) -> HealthResponse:
    return HealthResponse(
        status="ok",
        provider=game.provider.name,
        model=getattr(game.provider, "model", None),
    )


@router.post("/sessions", response_model=SessionResponse, status_code=201)
def new_session(body: NewSessionRequest, game: Game, request: Request) -> SessionResponse:
    try:
        session = game.create_session(body.nickname, client_ip=client_ip(request))
    except GameError as exc:
        raise _raise(exc) from None
    return SessionResponse(
        session_id=session.id, nickname=session.nickname, provider=game.provider.name
    )


@router.get("/levels", response_model=list[LevelOut])
def list_levels(game: Game, session_id: OptionalSession = None) -> list[LevelOut]:
    out = []
    for st in game.level_statuses(session_id):
        spec = st.spec
        out.append(
            LevelOut(
                id=spec.id,
                name=spec.name,
                guard_name=spec.guard_name,
                tagline=spec.tagline,
                defenses=list(spec.defenses),
                hint=spec.hint,
                unlocked=st.unlocked,
                solved=st.solved,
                attempts=st.attempts,
                guesses=st.guesses,
                explainer=ExplainerOut(**asdict(spec.explainer)) if st.solved else None,
            )
        )
    return out


@router.post("/levels/{level_id}/chat", response_model=ChatResponse)
async def chat(
    level_id: int, body: ChatRequest, game: Game, session_id: SessionHeader, request: Request
) -> ChatResponse:
    try:
        result = await game.chat(session_id, level_id, body.message, client_ip=client_ip(request))
    except GameError as exc:
        raise _raise(exc) from None
    return ChatResponse(
        reply=result.reply,
        blocked=result.blocked,
        caught_by=result.caught_by,
        reason=result.reason,
        outcome=result.outcome.value,
        techniques=result.techniques,
        attempts=result.attempts,
    )


@router.get("/levels/{level_id}/transcript", response_model=list[TranscriptItem])
def transcript(level_id: int, game: Game, session_id: SessionHeader) -> list[TranscriptItem]:
    try:
        rows = game.transcript(session_id, level_id)
    except GameError as exc:
        raise _raise(exc) from None
    return [
        TranscriptItem(
            prompt=r.prompt,
            response=r.response,
            blocked=r.outcome in ("blocked", "rate_limited"),
            caught_by=r.caught_by,
            outcome=r.outcome.value,
            techniques=r.techniques,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/levels/{level_id}/guess", response_model=GuessResponse)
def guess(
    level_id: int, body: GuessRequest, game: Game, session_id: SessionHeader
) -> GuessResponse:
    try:
        result = game.guess(session_id, level_id, body.password)
    except GameError as exc:
        raise _raise(exc) from None
    explainer = ExplainerOut(**asdict(get_level(level_id).explainer)) if result.correct else None
    return GuessResponse(**asdict(result), explainer=explainer)


@router.get("/leaderboard")
def leaderboard(game: Game, include_synthetic: IncludeSynthetic = True) -> list[dict[str, Any]]:
    return research.leaderboard(game.engine, include_synthetic=include_synthetic)


@router.get("/research/summary")
def research_summary(game: Game, include_synthetic: IncludeSynthetic = True) -> dict[str, Any]:
    return research.summary(game.engine, include_synthetic=include_synthetic)


@router.get("/research/export.jsonl")
def research_export(game: Game, include_synthetic: IncludeSynthetic = True) -> StreamingResponse:
    return StreamingResponse(
        research.export_jsonl(game.engine, include_synthetic=include_synthetic),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="gauntlet-attacks.jsonl"'},
    )
