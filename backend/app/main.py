"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import router
from app.config import Settings, get_settings
from app.db import init_db, make_engine
from app.providers.base import ChatProvider
from app.providers.factory import build_provider
from app.services.game import GameService


def create_app(settings: Settings | None = None, provider: ChatProvider | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db(engine)
        yield
        engine.dispose()

    app = FastAPI(title="Jailbreak Gauntlet", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Session-Id"],
    )
    app.state.game = GameService(engine, provider or build_provider(settings), settings)
    app.include_router(router)
    return app


app = create_app()
