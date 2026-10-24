"""Question catalog (knowledge_base/question_catalog.json): one reviewed follow-up
question per profile field. Models, criterion references and the KB fingerprint."""

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.knowledge_base.flat import FlatInstrument, ScopedCriterion

DONT_KNOW = "Weiss nicht"
FILTER_PREFIX = "filter"

type State = Literal["erfuellt", "annahme", "unbekannt", "nicht_erfuellt"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CatalogOption(_Model):
    label: str
    value: Any


class ValueRule(_Model):
    value: Any
    state: State


class RangeRule(_Model):
    """`min` inclusive, `max` exclusive, None = open. Dates as 'YYYY-MM' or 'heute'."""

    min: float | str | None
    max: float | str | None
    state: State


class Decision(_Model):
    criterion: str
    map: list[ValueRule | RangeRule]

    @property
    def states(self) -> set[State]:
        return {rule.state for rule in self.map}


class NotDecidable(_Model):
    criterion: str
    reason: str


class Generated(_Model):
    model: str
    prompt_version: str
    date: date


class Review(_Model):
    status: Literal["draft", "needs_review", "verified"]
    by: str | None
    date: date | None
    notes: str | None


class CatalogEntry(_Model):
    text: str
    why: str
    input: Literal["auswahl", "zahl", "datum"]
    unit: str | None
    min: float | None
    max: float | None
    options: list[CatalogOption]
    ask_if: list[Literal["fehlt", "annahme"]]
    decides: list[Decision]
    not_decidable: list[NotDecidable]
    kb_fingerprint: str
    generated: Generated | None
    review: Review

    def deciding(self) -> list[Decision]:
        """Decisions that can actually change a state: at least two different outcomes."""
        return [d for d in self.decides if len(d.states) >= 2]

    def option(self, label: str) -> CatalogOption | None:
        return next((o for o in self.options if o.label == label), None)


def criterion_ref(item: FlatInstrument, scoped: ScopedCriterion) -> str:
    """Catalog reference of a criterion: '<program>:<criterion>' or 'filter:<criterion>'."""
    owner = FILTER_PREFIX if scoped.scope == "filter" else item.program.id
    return f"{owner}:{scoped.criterion.id}"


def criteria_on_field(
    instruments: Iterable[FlatInstrument], field: str
) -> dict[str, list[tuple[FlatInstrument, ScopedCriterion]]]:
    """All criteria that use a profile field, by catalog reference."""
    found: dict[str, list[tuple[FlatInstrument, ScopedCriterion]]] = defaultdict(list)
    for item in instruments:
        for scoped in item.criteria():
            if field in scoped.criterion.profile_fields:
                found[criterion_ref(item, scoped)].append((item, scoped))
    return dict(found)


def fingerprint(instruments: Iterable[FlatInstrument], field: str) -> str:
    """Hash over every criterion the entry for `field` was built for. Changes when a
    criterion on the field is added, removed or reworded."""
    rows = set()
    for ref, occurrences in criteria_on_field(instruments, field).items():
        for item, scoped in occurrences:
            c = scoped.criterion
            instrument = None if scoped.scope == "programm" else item.instrument.id
            rows.add(
                json.dumps(
                    [ref, instrument, c.text, c.kind, c.applies_if, sorted(c.profile_fields)],
                    ensure_ascii=False,
                )
            )
    digest = hashlib.sha256("\n".join(sorted(rows)).encode()).hexdigest()
    return f"sha256:{digest}"
