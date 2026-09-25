from types import SimpleNamespace

import httpx
import pytest
from openai import BadRequestError, RateLimitError

from app.config import Settings
from app.providers.base import ChatMessage, ProviderError
from app.providers.factory import build_provider
from app.providers.jsonutil import parse_json_object
from app.providers.mock_provider import MockProvider
from app.providers.openai_provider import OpenAIProvider

GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _reply(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _http_error(cls, status):
    request = httpx.Request("POST", "https://example.test/chat/completions")
    return cls("boom", response=httpx.Response(status, request=request), body=None)


class FakeCompletions:
    """Replays a script of replies/exceptions and records every request."""

    def __init__(self, *script) -> None:
        self.script = list(script) or ["hi"]
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return _reply(item)


def make(*script, **kw) -> tuple[OpenAIProvider, FakeCompletions]:
    completions = FakeCompletions(*script)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    kw.setdefault("backoff_seconds", 0)
    return OpenAIProvider("test-key", "guard-model", client=client, **kw), completions


async def test_openai_request_shape_and_model_routing():
    provider, calls = make(models={"judge": "judge-model", "classifier": None})
    assert provider.name == "openai"
    assert (
        await provider.complete([ChatMessage("user", "hello")], purpose="judge", json_mode=True)
        == "hi"
    )
    req = calls.calls[-1]
    assert req["model"] == "judge-model"
    assert req["response_format"] == {"type": "json_object"}
    assert req["messages"] == [{"role": "user", "content": "hello"}]
    assert "max_completion_tokens" in req and "reasoning_effort" not in req
    await provider.complete([ChatMessage("user", "x")], purpose="classifier")
    assert calls.calls[-1]["model"] == "judge-model"  # labeler falls back to judge model
    await provider.complete([ChatMessage("user", "x")], purpose="quarantine")
    assert calls.calls[-1]["model"] == "guard-model"
    assert "response_format" not in calls.calls[-1]


async def test_compatible_endpoint_options():
    provider, calls = make(
        base_url=GEMINI,
        reasoning_effort="none",
        json_mode=False,
        models={"classifier": "labeler-model"},
    )
    assert provider.name == "openai-compatible"
    await provider.complete([ChatMessage("user", "x")], purpose="classifier", json_mode=True)
    req = calls.calls[-1]
    assert req["model"] == "labeler-model"
    assert "max_tokens" in req and "max_completion_tokens" not in req
    assert req["reasoning_effort"] == "none"
    assert "response_format" not in req  # JSON mode disabled for this endpoint


async def test_retries_rate_limits_then_succeeds():
    provider, calls = make(_http_error(RateLimitError, 429), "ok")
    assert await provider.complete([ChatMessage("user", "x")]) == "ok"
    assert len(calls.calls) == 2


async def test_gives_up_with_provider_error():
    provider, calls = make(_http_error(RateLimitError, 429))
    with pytest.raises(ProviderError):
        await provider.complete([ChatMessage("user", "x")])
    assert len(calls.calls) == 3


async def test_bad_request_is_not_retried():
    provider, calls = make(_http_error(BadRequestError, 400))
    with pytest.raises(ProviderError, match="HTTP 400"):
        await provider.complete([ChatMessage("user", "x")])
    assert len(calls.calls) == 1


async def test_empty_completion_is_retried():
    provider, calls = make(None, "", "finally")
    assert await provider.complete([ChatMessage("user", "x")]) == "finally"
    assert len(calls.calls) == 3


def test_factory_auto_falls_back_to_mock():
    assert isinstance(build_provider(Settings(provider="auto", openai_api_key=None)), MockProvider)
    provider = build_provider(
        Settings(provider="auto", openai_api_key="k", openai_base_url=GEMINI, openai_model="g")
    )
    assert isinstance(provider, OpenAIProvider) and provider.name == "openai-compatible"


def test_factory_openai_requires_key():
    with pytest.raises(RuntimeError):
        build_provider(Settings(provider="openai", openai_api_key=None))


def test_empty_env_values_mean_unset():
    s = Settings(openai_api_key="", openai_base_url=" ", openai_judge_model="")
    assert s.openai_api_key is None and s.openai_base_url is None and s.openai_judge_model is None
    assert s.resolved_provider == "mock"


@pytest.mark.parametrize(
    "raw",
    [
        '{"verdict": "allow"}',
        '```json\n{"verdict": "allow"}\n```',
        'Sure! Here is my answer: {"verdict": "allow"} Hope that helps.',
    ],
)
def test_parse_json_object_is_lenient(raw):
    assert parse_json_object(raw) == {"verdict": "allow"}


@pytest.mark.parametrize("raw", ["", "no json here", "[1, 2]", "{broken"])
def test_parse_json_object_rejects_garbage(raw):
    with pytest.raises(ValueError):
        parse_json_object(raw)


def _gemini_429(delay: str):
    request = httpx.Request("POST", "https://example.test/chat/completions")
    body = {
        "code": 429,
        "message": f"Quota exceeded for metric ... Please retry in {delay}s.",
        "status": "RESOURCE_EXHAUSTED",
    }
    return RateLimitError(
        f"Error code: 429 - {body}", response=httpx.Response(429, request=request), body=body
    )


def test_retry_after_parses_gemini_retry_info():
    from app.providers.openai_provider import retry_after_seconds

    assert retry_after_seconds(_gemini_429("29.93")) == pytest.approx(29.93)
    request = httpx.Request("POST", "https://example.test")
    exc = RateLimitError(
        "x",
        response=httpx.Response(429, request=request, headers={"retry-after": "7"}),
        body=None,
    )
    assert retry_after_seconds(exc) == 7
    assert retry_after_seconds(_http_error(RateLimitError, 429)) is None


async def test_long_server_requested_wait_fails_fast_then_falls_back():
    provider, calls = make(
        _gemini_429("3600"), "from fallback", fallback_models=["backup-model"], max_retry_wait=5
    )
    assert await provider.complete([ChatMessage("user", "x")]) == "from fallback"
    assert [c["model"] for c in calls.calls] == ["guard-model", "backup-model"]


async def test_retired_model_404_falls_back():
    from openai import NotFoundError

    provider, calls = make(_http_error(NotFoundError, 404), "ok", fallback_models=["new-model"])
    assert await provider.complete([ChatMessage("user", "x")]) == "ok"
    assert calls.calls[-1]["model"] == "new-model"
    await provider.complete([ChatMessage("user", "y")])
    assert [c["model"] for c in calls.calls] == ["guard-model", "new-model", "new-model"]


async def test_no_fallback_for_client_errors():
    provider, calls = make(_http_error(BadRequestError, 400), fallback_models=["other"])
    with pytest.raises(ProviderError):
        await provider.complete([ChatMessage("user", "x")])
    assert {c["model"] for c in calls.calls} == {"guard-model"}


async def test_model_rejecting_reasoning_effort_is_retried_without_it():
    request = httpx.Request("POST", "https://example.test")
    rejected = BadRequestError(
        "Thinking level MINIMAL is not supported for this model.",
        response=httpx.Response(400, request=request),
        body=None,
    )
    provider, calls = make(rejected, "ok", "ok", reasoning_effort="minimal", base_url=GEMINI)
    assert await provider.complete([ChatMessage("user", "x")]) == "ok"
    assert "reasoning_effort" in calls.calls[0] and "reasoning_effort" not in calls.calls[1]
    await provider.complete([ChatMessage("user", "y")])
    assert "reasoning_effort" not in calls.calls[2]  # remembered per model


def test_factory_parses_fallback_models():
    settings = Settings(
        openai_api_key="k",
        openai_base_url=GEMINI,
        openai_fallback_models=" gemini-a , ,gemini-b",
        _env_file=None,
    )
    provider = build_provider(settings)
    assert isinstance(provider, OpenAIProvider)
    assert provider._fallbacks == ["gemini-a", "gemini-b"]
