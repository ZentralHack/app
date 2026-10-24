"""Load and check the question catalog. A broken catalog never stops the server:
broken entries are dropped and their criteria fall back to `criteria[].question`."""

import json
import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
from pydantic import ValidationError

from app.knowledge_base.catalog import CatalogEntry
from app.knowledge_base.catalog_checks import STALE, Finding, check_catalog
from app.knowledge_base.flat import FlatInstrument
from app.models.program import Program

log = logging.getLogger(__name__)

CATALOG_FILE = "question_catalog.json"
CATALOG_SCHEMA = Path("schema") / "question_catalog.schema.json"


@dataclass(frozen=True)
class QuestionCatalog:
    entries: dict[str, CatalogEntry] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    error: str | None = None

    def review_counts(self) -> Counter[str]:
        """Entries per review status, plus `veraltet` for outdated fingerprints."""
        counts = Counter(e.review.status for e in self.entries.values())
        counts["veraltet"] = sum(f.message == STALE for f in self.findings)
        return counts


def load_question_catalog(
    directory: Path, programs: Sequence[Program], instruments: Sequence[FlatInstrument]
) -> QuestionCatalog:
    path = directory / CATALOG_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads((directory / CATALOG_SCHEMA).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return _failed(f"Fragenkatalog nicht lesbar: {error}")
    errors = [e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(raw)]
    if errors:
        return _failed(f"Fragenkatalog ungültig: {'; '.join(errors[:5])}")
    try:
        entries = {name: CatalogEntry.model_validate(e) for name, e in raw.items()}
    except ValidationError as error:
        return _failed(f"Fragenkatalog ungültig: {error}")

    findings = check_catalog(entries, programs, instruments)
    for finding in findings:
        level = logging.ERROR if finding.severity == "fehler" else logging.WARNING
        log.log(level, "Fragenkatalog %s: %s", finding.field, finding.message)
    broken = {f.field for f in findings if f.severity == "fehler"}
    usable = {name: e for name, e in entries.items() if name not in broken}
    return QuestionCatalog(usable, findings)


def _failed(message: str) -> QuestionCatalog:
    log.error("%s. Rückfragen nur aus criteria[].question.", message)
    return QuestionCatalog(error=message)
