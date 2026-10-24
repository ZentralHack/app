"""Deterministic LLM for tests and offline runs: returns prepared outputs per task."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from app.llm.client import Effort, Tier
from app.llm.schema import LLMOutput, strict_json_schema

type FakeResponse = LLMOutput | Callable[[str], LLMOutput]


@dataclass(frozen=True)
class FakeCall:
    task: str
    system: str
    user: str
    tier: Tier
    effort: Effort


@dataclass
class FakeLLM:
    """`responses` maps a task to an output, or to a function of the user message
    (which may raise to simulate a failing call)."""

    responses: Mapping[str, FakeResponse]
    calls: list[FakeCall] = field(default_factory=list)

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
        self.calls.append(FakeCall(task, system, user, tier, effort))
        response = self.responses[task]
        result = response(user) if callable(response) else response
        if not isinstance(result, output):
            raise TypeError(f"Fake für '{task}' liefert {type(result).__name__}, nicht {output}")
        return result
