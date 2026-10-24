"""OpenAI implementation of LLMClient: Responses API with Structured Outputs (strict).

- one call per `structured`, behind a semaphore of MAX_CONCURRENCY
- timeout LLM_TIMEOUT_S per attempt; timeouts and server errors are retried once
- invalid output is retried once, with the validation error appended to the input
- rate limits are retried with exponential backoff
- every call is logged with task, model, duration, tokens and estimated cost;
  never the key, never the prompt or the user's text
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import openai
from openai import AsyncOpenAI
from openai.types.responses import ParsedResponse
from pydantic import ValidationError

from app.config import Settings
from app.llm.client import Effort, Tier, model_for_tier
from app.llm.errors import LLMOutputError, LLMUnavailableError, RefusalError
from app.llm.schema import LLMOutput, strict_json_schema
from app.llm.usage import CallRecord, record

log = logging.getLogger(__name__)

RATE_LIMIT_DELAYS_S = (2.0, 4.0, 8.0)
TRANSIENT = (openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError)
NOT_AVAILABLE = (openai.AuthenticationError, openai.PermissionDeniedError, openai.NotFoundError)

UNAVAILABLE = "Die KI ist im Moment nicht erreichbar. Bitte versuchen Sie es später nochmals."
INVALID = "Die KI hat keine gültige Antwort geliefert."
REFUSED = "Die KI hat die Anfrage abgelehnt."


@dataclass
class _Tally:
    attempts: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, response: ParsedResponse) -> None:
        if response.usage:
            self.input_tokens += response.usage.input_tokens
            self.output_tokens += response.usage.output_tokens


class _InvalidOutput(Exception):
    """One attempt returned unusable output; the reason goes back to the model."""


class OpenAIClient:
    def __init__(
        self,
        settings: Settings,
        client: AsyncOpenAI | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if client is None:
            if settings.openai_api_key is None:
                raise LLMUnavailableError("OPENAI_API_KEY ist nicht gesetzt.", retryable=False)
            client = AsyncOpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                timeout=settings.llm_timeout_s,
                max_retries=0,  # retries are handled here, with logging
            )
        self._client = client
        self._settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        self._sleep = sleep

    async def structured[T: LLMOutput](
        self,
        *,
        task: str,
        system: str,
        user: str,
        output: type[T],
        tier: Tier,
        effort: Effort,
    ) -> T:
        strict_json_schema(output)
        model = model_for_tier(self._settings, tier)
        async with self._semaphore:
            started = time.monotonic()
            tally = _Tally()
            try:
                return await self._attempts(model, system, user, output, effort, tally)
            finally:
                self._log(task, model, tier, started, tally)

    async def _attempts[T: LLMOutput](
        self, model: str, system: str, user: str, output: type[T], effort: Effort, tally: _Tally
    ) -> T:
        hint: str | None = None
        transient_left, rate_limit_delays = 1, list(RATE_LIMIT_DELAYS_S)
        while True:
            tally.attempts += 1
            prompt = user if hint is None else f"{user}\n\n{hint}"
            try:
                response = await self._client.responses.parse(
                    model=model,
                    instructions=system,
                    input=prompt,
                    text_format=output,
                    reasoning={"effort": effort},
                    store=False,
                )
                tally.add(response)
                return _parsed(response, output)
            except (_InvalidOutput, ValidationError) as error:
                if hint is not None:
                    raise LLMOutputError(INVALID) from error
                hint = _retry_hint(error)
            except openai.RateLimitError as error:
                if not rate_limit_delays:
                    raise LLMUnavailableError(UNAVAILABLE) from error
                await self._sleep(rate_limit_delays.pop(0))
            except TRANSIENT as error:
                if not transient_left:
                    raise LLMUnavailableError(UNAVAILABLE) from error
                transient_left -= 1
            except NOT_AVAILABLE as error:
                raise LLMUnavailableError(UNAVAILABLE, retryable=False) from error
            except openai.APIStatusError as error:
                log.error("LLM-Anfrage abgelehnt: HTTP %s", error.status_code)
                raise LLMOutputError(INVALID, retryable=False) from error

    def _log(self, task: str, model: str, tier: Tier, started: float, tally: _Tally) -> None:
        price_in, price_out = (
            self._settings.price_small_usd if tier == "small" else self._settings.price_main_usd
        )
        call = CallRecord(
            task=task,
            model=model,
            tier=tier,
            duration_ms=round((time.monotonic() - started) * 1000),
            input_tokens=tally.input_tokens,
            output_tokens=tally.output_tokens,
            cost_usd=(tally.input_tokens * price_in + tally.output_tokens * price_out) / 1_000_000,
            attempts=tally.attempts,
        )
        record(call)
        log.info(
            "LLM %s model=%s dauer_ms=%d tokens_in=%d tokens_out=%d kosten_usd=%.5f versuche=%d",
            call.task,
            call.model,
            call.duration_ms,
            call.input_tokens,
            call.output_tokens,
            call.cost_usd,
            call.attempts,
        )


def _parsed[T: LLMOutput](response: ParsedResponse[T], output: type[T]) -> T:
    for item in response.output:
        if item.type == "message":
            for content in item.content:
                if content.type == "refusal":
                    raise RefusalError(REFUSED, retryable=False)
    if response.status == "incomplete":
        reason = response.incomplete_details.reason if response.incomplete_details else None
        raise _InvalidOutput(f"Antwort unvollständig ({reason})")
    parsed = response.output_parsed
    if not isinstance(parsed, output):
        raise _InvalidOutput("keine strukturierte Antwort")
    return parsed


def _retry_hint(error: Exception) -> str:
    """Field locations and error types only, no content."""
    if isinstance(error, ValidationError):
        details = "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in error.errors()[:10]
        )
    else:
        details = str(error)
    return (
        f"Deine letzte Antwort war ungültig ({details}). "
        "Antworte nochmals, vollständig und genau nach dem Schema."
    )
