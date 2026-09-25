"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import router
from app.config import Settings, get_settings
from app.db import init_db, make_engine
from app.providers.base import ChatProvider
from app.providers.factory import build_provider
from app.services.game import GameService

log = logging.getLogger("gauntlet")


def create_app(settings: Settings | None = None, provider: ChatProvider | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.resolved_database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db(engine)
        if settings.seed_on_startup:
            from app.admin import has_synthetic, seed_synthetic

            if not has_synthetic(engine):
                n = await seed_synthetic(engine, settings, players=settings.seed_players)
                log.info("seeded %d synthetic attempts", n)
        yield
        engine.dispose()

    docs = settings.docs_enabled
    app = FastAPI(
        title="Jailbreak Gauntlet",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Session-Id"],
    )
    app.state.game = GameService(engine, provider or build_provider(settings), settings)
    app.include_router(router)
    if settings.admin_enabled:
        from app.admin import router as admin_router

        app.include_router(admin_router)
    if settings.static_dir:
        mount_frontend(app, Path(settings.static_dir))
    return app


def mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built SPA: real files if they exist, else index.html (client routing)."""
    index = dist / "index.html"
    if not index.is_file():
        raise RuntimeError(f"STATIC_DIR={dist} has no index.html - build the frontend first")
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    root = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
