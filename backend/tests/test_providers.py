from types import SimpleNamespace

import pytest

from app.config import Settings
from app.providers.base import ChatMessage
from app.providers.factory import build_provider
from app.providers.mock_provider import MockProvider
from app.providers.openai_provider import OpenAIProvider


class FakeCompletions:
    def __init__(self) -> None:
        self.kwargs: dict = {}

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))])


def fake_client() -> tuple[SimpleNamespace, FakeCompletions]:
    completions = FakeCompletions()
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


async def test_openai_provider_request_shape():
    client, completions = fake_client()
    provider = OpenAIProvider("sk-test", "guard-model", judge_model="judge-model", client=client)
    out = await provider.complete([ChatMessage("user", "hello")], purpose="judge", json_mode=True)
    assert out == "hi"
    assert completions.kwargs["model"] == "judge-model"
    assert completions.kwargs["response_format"] == {"type": "json_object"}
    assert completions.kwargs["messages"] == [{"role": "user", "content": "hello"}]
    await provider.complete([ChatMessage("user", "x")])
    assert completions.kwargs["model"] == "guard-model"
    assert "response_format" not in completions.kwargs


def test_factory_auto_falls_back_to_mock():
    assert isinstance(build_provider(Settings(provider="auto", openai_api_key=None)), MockProvider)
    assert isinstance(
        build_provider(Settings(provider="auto", openai_api_key="sk-x")), OpenAIProvider
    )


def test_factory_openai_requires_key():
    with pytest.raises(RuntimeError):
        build_provider(Settings(provider="openai", openai_api_key=None))
