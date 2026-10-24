"""Validate data against a definition in design/contract.schema.json."""

import json
from functools import cache
from typing import Any

import jsonschema
from pydantic import BaseModel
from referencing import Registry, Resource

from app.config import CONTRACT_SCHEMA


@cache
def contract_validator(definition: str) -> jsonschema.Draft202012Validator:
    schema = json.loads(CONTRACT_SCHEMA.read_text(encoding="utf-8"))
    registry = Registry().with_resource("contract.schema.json", Resource.from_contents(schema))
    return jsonschema.Draft202012Validator(
        {"$ref": f"contract.schema.json#/$defs/{definition}"},
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    )


def assert_contract(definition: str, data: Any) -> None:
    """Fails with every schema error; models are dumped as JSON first."""
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")
    errors = [
        f"{list(e.absolute_path)}: {e.message}"
        for e in contract_validator(definition).iter_errors(data)
    ]
    assert errors == [], errors
