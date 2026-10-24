"""OpenAIClient against a mocked HTTP transport: the real SDK parse path, no network."""

import asyncio
import json
from collections.abc import Callable

import httpx2
import pytest
from openai import AsyncOpenAI

from app.config import Settings
from app.llm.errors import LLMOutputError, LLMUnavailableError, RefusalError
from app.llm.openai_client import OpenAIClient
from app.llm.schema import LLMOutput
from app.llm.usage import Usage, current_usage


class Answer(LLMOutput):
    word: str
    count: int


SETTINGS = Settings(
    _env_file=None, openai_api_key="sk-test", model_extract="klein", model_reason="gross"
)


def _response(text: str | None = None, *, refusal: str | None = None, status="completed"):
    content = (
        {"type": "refusal", "refusal": refusal}
        if refusal
        else {"type": "output_text", "text": text, "annotations": []}
    )
    return {
        "id": "resp_1",
        "object": "response",
        "created_at": 0,
        "status": status,
        "incomplete_details": {"reason": "max_output_tokens"} if status == "incomplete" else None,
        "model": "gross",
        "output": [
            {
                "type": "message",
                "id": "msg_1",
                "status": "completed",
                "role": "assistant",
                "content": [content],
            }
        ],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "usage": {
            "input_tokens": 1000,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 100,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 1100,
        },
    }


class Server:
    """Answers each request with the next prepared reply and records the request bodies."""

    def __init__(self, *replies: dict | int | Callable[[], None]):
        self.replies = list(replies)
        self.requests: list[dict] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content))
        reply = self.replies.pop(0)
        if isinstance(reply, int):
            return httpx2.Response(reply, json={"error": {"message": "x", "type": "x"}})
        if callable(reply):
            reply()
        return httpx2.Response(200, json=reply)


def _client(server: Server, sleeps: list[float] | None = None) -> OpenAIClient:
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(server))
    sdk = AsyncOpenAI(api_key="sk-test", http_client=http, max_retries=0)

    async def sleep(seconds: float) -> None:
        (sleeps if sleeps is not None else []).append(seconds)

    return OpenAIClient(SETTINGS, client=sdk, sleep=sleep)


def _ask(client: OpenAIClient, tier="main") -> Answer:
    return asyncio.run(
        client.structured(
            task="test", system="System", user="Frage", output=Answer, tier=tier, effort="low"
        )
    )


OK = _response('{"word": "Sensor", "count": 2}')


def test_parses_strict_output_and_sends_settings():
    server = Server(OK)
    assert _ask(_client(server)) == Answer(word="Sensor", count=2)
    body = server.requests[0]
    assert body["model"] == "gross"
    assert body["instructions"] == "System"
    assert body["reasoning"] == {"effort": "low"}
    assert body["text"]["format"]["strict"] is True
    assert body["text"]["format"]["schema"]["additionalProperties"] is False


def test_small_tier_uses_extract_model():
    server = Server(OK)
    _ask(_client(server), tier="small")
    assert server.requests[0]["model"] == "klein"


def test_invalid_output_is_retried_once_with_hint():
    server = Server(_response('{"word": "Sensor"}'), OK)
    assert _ask(_client(server)).count == 2
    assert "ungültig" in server.requests[1]["input"]
    assert "count" in server.requests[1]["input"]


def test_invalid_output_twice_fails():
    bad = _response('{"word": 1}')
    with pytest.raises(LLMOutputError):
        _ask(_client(Server(bad, bad)))


def test_incomplete_output_counts_as_invalid():
    cut = _response('{"word": "Sen', status="incomplete")
    assert _ask(_client(Server(cut, OK))).word == "Sensor"


def test_refusal_is_a_typed_error():
    with pytest.raises(RefusalError):
        _ask(_client(Server(_response(refusal="Nein"))))


def test_rate_limit_backs_off():
    sleeps: list[float] = []
    assert _ask(_client(Server(429, 429, OK), sleeps)).word == "Sensor"
    assert sleeps == [2.0, 4.0]


def test_rate_limit_exhausted():
    with pytest.raises(LLMUnavailableError):
        _ask(_client(Server(429, 429, 429, 429)))


def test_server_error_is_retried_once():
    assert _ask(_client(Server(500, OK))).word == "Sensor"
    with pytest.raises(LLMUnavailableError) as error:
        _ask(_client(Server(500, 503)))
    assert error.value.retryable


def test_auth_error_is_not_retried():
    server = Server(401, OK)
    with pytest.raises(LLMUnavailableError) as error:
        _ask(_client(server))
    assert not error.value.retryable
    assert len(server.requests) == 1


def test_usage_and_cost_are_recorded(caplog):
    usage = Usage()
    token = current_usage.set(usage)
    try:
        with caplog.at_level("INFO"):
            _ask(_client(Server(OK)))
    finally:
        current_usage.reset(token)
    (call,) = usage.calls
    assert (call.input_tokens, call.output_tokens, call.attempts) == (1000, 100, 1)
    assert call.cost_usd == pytest.approx((1000 * 2.0 + 100 * 10.0) / 1_000_000)
    assert "Frage" not in caplog.text
    assert "sk-test" not in caplog.text


def test_missing_key_or_model():
    with pytest.raises(LLMUnavailableError):
        OpenAIClient(Settings(_env_file=None))
    client = OpenAIClient(Settings(_env_file=None, openai_api_key="sk-test"))
    with pytest.raises(LLMUnavailableError, match="MODEL_REASON"):
        _ask(client)
