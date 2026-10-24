"""The one interface every model call goes through. Provider: OpenAI (LLM_PROVIDER).

Output models must work with OpenAI Structured Outputs in strict mode: every field
required (no defaults), `None` instead of leaving a field out, `additionalProperties: false`.
Derive them from `LLMOutput`; `strict_json_schema` checks this before every call.
"""

from typing import Literal, Protocol

from app.config import Settings
from app.llm.errors import LLMUnavailableError
from app.llm.schema import LLMOutput

type Tier = Literal["main", "small"]
type Effort = Literal["none", "low", "medium", "high"]


class LLMClient(Protocol):
    async def structured[T: LLMOutput](
        self,
        *,
        task: str,  # "profile", "matching", ... for logging and tracing
        system: str,  # stable prompt, cacheable
        user: str,  # per-call content
        output: type[T],
        tier: Tier,
        effort: Effort,  # reasoning effort for this call
    ) -> T: ...


def model_for_tier(settings: Settings, tier: Tier) -> str:
    """`small` → MODEL_EXTRACT (profile extraction), `main` → MODEL_REASON (everything else).
    Model ids live only in the environment, never in code."""
    model = settings.model_extract if tier == "small" else settings.model_reason
    if not model:
        variable = "MODEL_EXTRACT" if tier == "small" else "MODEL_REASON"
        raise LLMUnavailableError(f"{variable} ist nicht gesetzt.", retryable=False)
    return model
