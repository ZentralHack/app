"""Step 2 (questions), pure code. Picks the follow-up questions whose answer can change
a fit level. No LLM call.

Source of a question: the question catalog entry of a profile field, if it decides the
criterion; otherwise the criterion's own `criteria[].question`.

Points per question: +3 per instrument where it decides a `muss` criterion, +1 for `soll`,
+2 if the instrument has a lever on that criterion; half the points if the field is only
`annahme`. Questions with at least MIN_POINTS are asked, highest first, at most
`max_questions`.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.agent.prefilter import prefilter
from app.agent.profile_values import known
from app.knowledge_base.catalog import CatalogEntry, criterion_ref
from app.knowledge_base.flat import FlatInstrument, ScopedCriterion
from app.knowledge_base.loader import KnowledgeBase
from app.knowledge_base.questions import CriterionQuestion
from app.models.contract import CriterionRef, ProjectProfile, Question, QuestionSet

MAX_QUESTIONS = 10
MIN_POINTS = 3
KIND_POINTS = {"muss": 3, "soll": 1, "bewertung": 0}
LEVER_POINTS = 2
ASSUMED_WEIGHT = 0.5

SKIP_REASON = "Keine Rückfrage würde die Einstufung eines Programms ändern."


@dataclass
class _Candidate:
    """A question being scored. `draft` holds every Question field but `affects`."""

    draft: dict[str, Any]
    points: float = 0
    affects: list[CriterionRef] = field(default_factory=list)
    instrument_names: list[str] = field(default_factory=list)

    def add(self, item: FlatInstrument, scoped: ScopedCriterion, weight: float) -> None:
        criterion = scoped.criterion
        points = KIND_POINTS[criterion.kind]
        if item.levers_for(criterion.id):
            points += LEVER_POINTS
        self.points += points * weight
        ref = CriterionRef(
            program_id=item.program.id,
            instrument_id=None if scoped.scope == "programm" else item.instrument.id,
            criterion_id=criterion.id,
        )
        if ref not in self.affects:
            self.affects.append(ref)
        if item.instrument.name not in self.instrument_names:
            self.instrument_names.append(item.instrument.name)


def build_questions(profile: ProjectProfile, kb: KnowledgeBase) -> QuestionSet:
    """Questions for the instruments that survive the pre-filter with this profile."""
    candidates = prefilter(profile, kb.instruments()).kept
    return select_questions(profile, candidates, kb.catalog.entries, kb.criterion_questions)


def select_questions(
    profile: ProjectProfile,
    candidates: Iterable[FlatInstrument],
    catalog: dict[str, CatalogEntry],
    fallback: dict[str, CriterionQuestion],
    max_questions: int = MAX_QUESTIONS,
) -> QuestionSet:
    """`candidates` are the instruments that survived the pre-filter."""
    decided_by = _decided_by(catalog)
    scored: dict[str, _Candidate] = {}
    for item in candidates:
        for scoped in item.criteria():
            fields = decided_by.get(criterion_ref(item, scoped), [])
            for name in fields:
                weight = _ask_weight(profile, name, catalog[name])
                if weight:
                    key = f"q_{name}"
                    if key not in scored:
                        scored[key] = _Candidate(_catalog_question(profile, name, catalog[name]))
                    scored[key].add(item, scoped, weight)
            question = fallback.get(scoped.criterion.id)
            if not fields and question and _fallback_open(profile, scoped, question):
                key = f"q_{question.criterion_id}"
                scored.setdefault(key, _Candidate(_fallback_question(question)))
                scored[key].add(item, scoped, 1)

    ranked = sorted(
        (c for c in scored.values() if c.points >= MIN_POINTS), key=lambda c: -c.points
    )[:max_questions]
    return QuestionSet(
        questions=[_finish(c) for c in ranked],
        skip_reason=None if ranked else SKIP_REASON,
    )


def _decided_by(catalog: dict[str, CatalogEntry]) -> dict[str, list[str]]:
    """Criterion reference → catalog fields whose question decides it."""
    index: dict[str, list[str]] = defaultdict(list)
    for name, entry in catalog.items():
        for decision in entry.deciding():
            index[decision.criterion].append(name)
    return index


def _ask_weight(profile: ProjectProfile, name: str, entry: CatalogEntry) -> float:
    field_ = profile.fields.get(name)
    status = field_.status if field_ else "fehlt"
    if status not in entry.ask_if:
        return 0
    return ASSUMED_WEIGHT if status == "annahme" else 1


def _fallback_open(
    profile: ProjectProfile, scoped: ScopedCriterion, question: CriterionQuestion
) -> bool:
    """Not answered yet, and the profile cannot decide the criterion on its own."""
    if known(profile, question.profile_field) is not None:
        return False
    fields = scoped.criterion.profile_fields
    return not fields or any(known(profile, name) is None for name in fields)


def _catalog_question(profile: ProjectProfile, name: str, entry: CatalogEntry) -> dict[str, Any]:
    return {
        "id": f"q_{name}",
        "profile_field": name,
        "text": entry.text,
        "why": entry.why,
        "input": entry.input,
        "unit": entry.unit,
        "options": [o.label for o in entry.options],
        "prefill": _prefill(profile, name, entry),
    }


def _prefill(profile: ProjectProfile, name: str, entry: CatalogEntry) -> str | None:
    """The assumed answer, preselected when the field is `annahme`."""
    field_ = profile.fields.get(name)
    if field_ is None or field_.status != "annahme" or field_.value is None:
        return None
    if entry.input != "auswahl":
        return str(field_.value)
    return next((o.label for o in entry.options if o.value == field_.value), None)


def _fallback_question(question: CriterionQuestion) -> dict[str, Any]:
    return {
        "id": f"q_{question.criterion_id}",
        "profile_field": question.profile_field,
        "text": question.text,
        "why": "",
        "input": "auswahl",
        "unit": None,
        "options": list(question.options),
        "prefill": None,
    }


def _finish(candidate: _Candidate) -> Question:
    names = f"Entscheidet über: {', '.join(candidate.instrument_names)}."
    why = f"{candidate.draft['why']} {names}".strip()
    return Question(**candidate.draft | {"why": why, "affects": candidate.affects})
