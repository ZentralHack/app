"""Regenerate app/models/contract.py from design/contract.schema.json.

Run from backend/:  uv run python scripts/generate_contract_models.py
"""

import re
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCHEMA = BACKEND_DIR.parent / "design" / "contract.schema.json"
TARGET = BACKEND_DIR / "app" / "models" / "contract.py"

# Inline objects (e.g. the `data` of each event) get unique names only with the
# parent-prefixed strategy. The common prefix of the root model is stripped afterwards.
ROOT_NAME = "Contract"

# Everything a client sends: validated strictly (no "18" → 18), unknown keys rejected.
STRICT_MODELS = (
    "ProfileField",
    "ProjectProfile",
    "ProfileRequest",
    "QuestionsRequest",
    "Answer",
    "RunRequest",
    "RetryRequest",
    "ChatMessage",
    "ChatRequest",
)

CODEGEN_ARGS = [
    "--input-file-type", "jsonschema",
    "--output-model-type", "pydantic_v2.BaseModel",
    "--target-python-version", "3.13",
    "--use-standard-collections",
    "--use-union-operator",
    "--use-double-quotes",
    "--use-annotated",
    "--field-constraints",
    "--use-schema-description",
    "--enum-field-as-literal", "all",
    "--disable-timestamp",
    "--naming-strategy", "parent-prefixed",
    "--class-name", ROOT_NAME,
    "--formatters", "ruff-format", "ruff-check",
]  # fmt: skip


def main() -> None:
    subprocess.run(
        ["datamodel-codegen", "--input", str(SCHEMA), "--output", str(TARGET), *CODEGEN_ARGS],
        check=True,
    )
    code = TARGET.read_text(encoding="utf-8")
    code = re.sub(rf"\b{ROOT_NAME}(?=[A-Z])", "", code)
    for name in STRICT_MODELS:
        code, count = re.subn(
            rf"(class {name}\(BaseModel\):(?:\n.*?)*?model_config = ConfigDict\(\n)",
            r"\1        strict=True,\n",
            code,
            count=1,
        )
        if count != 1:
            raise SystemExit(f"{name}: model_config not found")
    TARGET.write_text(code, encoding="utf-8")
    print(f"{TARGET.relative_to(BACKEND_DIR)} written", file=sys.stderr)


if __name__ == "__main__":
    main()
