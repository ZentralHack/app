"""Token usage and estimated cost per LLM call, collected per run via a context variable."""

from contextvars import ContextVar
from dataclasses import dataclass, field

from app.llm.client import Tier


@dataclass(frozen=True)
class CallRecord:
    task: str
    model: str
    tier: Tier
    duration_ms: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    attempts: int


@dataclass
class Usage:
    calls: list[CallRecord] = field(default_factory=list)

    @property
    def input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)


current_usage: ContextVar[Usage | None] = ContextVar("current_usage", default=None)


def record(call: CallRecord) -> None:
    usage = current_usage.get()
    if usage is not None:
        usage.calls.append(call)
