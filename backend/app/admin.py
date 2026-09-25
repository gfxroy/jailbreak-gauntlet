"""Development-only admin endpoints. Not mounted when APP_ENV=production."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import Engine
from sqlmodel import Session, col, delete, select

from app.config import Settings
from app.models import Attempt, GameSession, LevelProgress
from app.providers.mock_provider import MockProvider

router = APIRouter(prefix="/api/admin", tags=["admin"])


def wipe_synthetic(engine: Engine) -> int:
    with Session(engine) as db:
        ids = list(db.exec(select(GameSession.id).where(col(GameSession.synthetic).is_(True))))
        if ids:
            db.exec(delete(Attempt).where(Attempt.session_id.in_(ids)))  # type: ignore[attr-defined]
            db.exec(delete(LevelProgress).where(LevelProgress.session_id.in_(ids)))  # type: ignore[attr-defined]
            db.exec(delete(GameSession).where(GameSession.id.in_(ids)))  # type: ignore[attr-defined]
            db.commit()
        return len(ids)


def has_synthetic(engine: Engine) -> bool:
    with Session(engine) as db:
        return (
            db.exec(select(GameSession.id).where(col(GameSession.synthetic).is_(True))).first()
            is not None
        )


async def seed_synthetic(engine: Engine, settings: Settings, players: int, seed: int = 7) -> int:
    import random

    from app.limits import LimitConfig, UsageLimiter
    from app.services.game import GameService
    from scripts.seed import simulate

    service = GameService(
        engine,
        MockProvider(),
        settings,
        limiter=UsageLimiter(LimitConfig(enabled=False)),
    )
    service.throttle.max_requests = 10**9
    _, attempts = await simulate(service, random.Random(seed), players, 14)
    return attempts


@router.post("/seed")
async def seed(
    request: Request, players: Annotated[int, Query(ge=1, le=200)] = 40
) -> dict[str, int]:
    game = request.app.state.game
    return {"attempts": await seed_synthetic(game.engine, game.settings, players)}


@router.delete("/synthetic")
def delete_synthetic(request: Request) -> dict[str, int]:
    return {"deleted_sessions": wipe_synthetic(request.app.state.game.engine)}
