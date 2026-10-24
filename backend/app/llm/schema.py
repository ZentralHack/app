"""Output models for structured LLM calls and the strict-mode check."""

from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, ConfigDict


class LLMOutput(BaseModel):
    """Base for every LLM output model. Declare fields without defaults; use
    `X | None` for optional values."""

    model_config = ConfigDict(extra="forbid")


class StrictSchemaError(TypeError):
    pass


# Not supported by OpenAI Structured Outputs in strict mode.
UNSUPPORTED_KEYWORDS = frozenset(
    {"allOf", "not", "if", "then", "else", "dependentRequired", "dependentSchemas"}
)


def strict_json_schema(output: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema of `output`, or StrictSchemaError if it is not valid for strict mode."""
    schema = output.model_json_schema()
    problems = list(_problems(schema, output.__name__))
    if "anyOf" in schema:
        problems.append("Wurzel darf kein anyOf sein")
    if problems:
        raise StrictSchemaError(f"{output.__name__} ist nicht strict: " + "; ".join(problems))
    return schema


def _problems(node: Any, path: str) -> Iterator[str]:
    if isinstance(node, list):
        for index, item in enumerate(node):
            yield from _problems(item, f"{path}[{index}]")
        return
    if not isinstance(node, dict):
        return
    for keyword in UNSUPPORTED_KEYWORDS & node.keys():
        yield f"{path}: {keyword} nicht unterstützt"
    if node.get("type") == "object":
        properties = node.get("properties", {})
        if node.get("additionalProperties") is not False:
            yield f"{path}: additionalProperties muss false sein"
        missing = sorted(set(properties) - set(node.get("required", [])))
        if missing:
            yield f"{path}: nicht required: {', '.join(missing)}"
    for key, child in node.items():
        if key != "default":
            yield from _problems(child, f"{path}.{key}")
