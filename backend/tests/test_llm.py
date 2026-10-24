import asyncio
from typing import Literal

import pytest
from pydantic import ConfigDict

from app.config import Settings
from app.llm.client import LLMClient, model_for_tier
from app.llm.errors import LLMUnavailableError
from app.llm.fake import FakeLLM
from app.llm.schema import LLMOutput, StrictSchemaError, strict_json_schema


class Check(LLMOutput):
    criterion_id: str
    state: Literal["erfuellt", "annahme", "unbekannt", "nicht_erfuellt"]
    evidence: list[str]
    note: str | None


class Checks(LLMOutput):
    checks: list[Check]
    lever_ids: list[str]


class WithDefault(LLMOutput):
    reason: str | None = None


class Nested(LLMOutput):
    inner: WithDefault


class Loose(LLMOutput):
    model_config = ConfigDict(extra="allow")
    reason: str


class FreeMap(LLMOutput):
    values: dict[str, str]


def test_strict_model_passes():
    schema = strict_json_schema(Checks)
    check = schema["$defs"]["Check"]
    assert check["additionalProperties"] is False
    assert set(check["required"]) == {"criterion_id", "state", "evidence", "note"}


@pytest.mark.parametrize(
    ("model", "problem"),
    [
        (WithDefault, "nicht required: reason"),
        (Nested, "nicht required: reason"),
        (Loose, "additionalProperties"),
        (FreeMap, "additionalProperties"),
    ],
)
def test_non_strict_models_are_rejected(model, problem):
    with pytest.raises(StrictSchemaError, match=problem):
        strict_json_schema(model)


def test_tiers_map_to_model_settings():
    settings = Settings(_env_file=None, model_extract="klein", model_reason="gross")
    assert model_for_tier(settings, "small") == "klein"
    assert model_for_tier(settings, "main") == "gross"
    with pytest.raises(LLMUnavailableError, match="MODEL_REASON"):
        model_for_tier(Settings(_env_file=None), "main")


def test_fake_returns_prepared_output_and_records_calls():
    expected = Checks(checks=[], lever_ids=[])
    llm: LLMClient = FakeLLM({"matching": expected, "profile": lambda user: expected})
    result = asyncio.run(
        llm.structured(
            task="matching", system="s", user="u", output=Checks, tier="main", effort="low"
        )
    )
    assert result is expected
    assert [(c.task, c.tier) for c in llm.calls] == [("matching", "main")]


def _call(llm: FakeLLM, task: str, output: type[LLMOutput]) -> LLMOutput:
    return asyncio.run(
        llm.structured(task=task, system="", user="", output=output, tier="main", effort="low")
    )


def test_fake_checks_strictness_and_type():
    checks = Checks(checks=[], lever_ids=[])
    llm = FakeLLM({"profile": WithDefault(reason=None), "matching": checks})
    with pytest.raises(StrictSchemaError):
        _call(llm, "profile", WithDefault)
    with pytest.raises(TypeError):
        _call(llm, "matching", Check)
