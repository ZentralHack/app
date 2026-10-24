"""Contract models round-trip the examples; program models fit the program schema."""

import json
import typing
from pathlib import Path

import pytest

from app.config import KNOWLEDGE_BASE_DIR, REPO_DIR
from app.models import contract, program
from tests.contract_check import contract_validator

EXAMPLES = sorted((REPO_DIR / "design" / "examples").glob("*.json"))
EXAMPLE_MODELS = {
    "profile_response": "ProfileResponse",
    "question_set": "QuestionSet",
    "run_request": "RunRequest",
    "run_result": "RunResult",
    "trace_events": "TraceEvent",
}


def test_every_example_has_a_model():
    assert {path.stem for path in EXAMPLES} == set(EXAMPLE_MODELS)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_round_trip(path: Path):
    name = EXAMPLE_MODELS[path.stem]
    model = getattr(contract, name)
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else [raw]
    validator = contract_validator(name)
    for item in items:
        dumped = model.model_validate(item).model_dump(mode="json")
        assert list(validator.iter_errors(dumped)) == []
        assert dumped == item


def _schema_enum(schema: dict, *path: str) -> list[str]:
    node = schema["$defs"]["instrument"]["properties"]["filter"]["properties"]
    for key in path:
        node = node[key]
    return node["items"]["enum"]


@pytest.mark.parametrize(
    ("literal", "field"),
    [
        (program.ApplicantType, "applicant_types"),
        (program.ProjectType, "project_types"),
        (program.RequiredPartner, "required_partners"),
        (program.Sector, "sectors"),
    ],
)
def test_filter_enums_match_program_schema(literal, field):
    schema = json.loads(
        (KNOWLEDGE_BASE_DIR / "schema" / "program.schema.json").read_text(encoding="utf-8")
    )
    assert list(typing.get_args(literal)) == _schema_enum(schema, field)


@pytest.mark.parametrize(
    "path", sorted((KNOWLEDGE_BASE_DIR / "programs").glob("*.json")), ids=lambda p: p.stem
)
def test_program_files_parse(path: Path):
    parsed = program.Program.model_validate_json(path.read_bytes())
    assert parsed.id == path.stem
