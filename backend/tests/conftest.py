from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.defenses.base import GuardContext
from app.defenses.prompts import base_prompt
from app.main import create_app
from app.providers.base import ChatMessage, Purpose
from app.providers.mock_provider import MockProvider

SECRET = "CASCADE"


class ScriptedProvider:
    """Returns canned replies per purpose and records every call."""

    name = "scripted"

    def __init__(self, replies: dict[str, str] | None = None) -> None:
        self.replies = replies or {}
        self.calls: list[tuple[Purpose, list[ChatMessage]]] = []

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        purpose: Purpose = "guard",
        json_mode: bool = False,
    ) -> str:
        self.calls.append((purpose, list(messages)))
        return self.replies.get(purpose, "ok")


@pytest.fixture
def mock_provider() -> MockProvider:
    return MockProvider()


@pytest.fixture
def make_ctx() -> Callable[..., GuardContext]:
    def factory(user_input: str, provider=None, secret: str = SECRET, **kw) -> GuardContext:
        return GuardContext(
            level=kw.pop("level", 1),
            secret=secret,
            user_input=user_input,
            provider=provider or MockProvider(),
            system_prompt_parts=[base_prompt("Tester", secret)],
            **kw,
        )

    return factory


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        provider="mock",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        rate_limit_max_requests=3,
        rate_limit_window_seconds=60,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as c:
        yield c
