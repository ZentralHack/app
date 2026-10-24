"""Step 2 (questions), pure code. Picks the follow-up questions whose answer can change
a fit level, from the question index built at startup. No LLM call.

Points per question: +3 per instrument where it decides a `muss` criterion, +1 for `soll`,
+2 if the instrument has a lever on that criterion. Questions with at least MIN_POINTS
are asked, highest first, at most `max_questions`.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.agent.profile_values import known
from app.knowledge_base.flat import FlatInstrument, ScopedCriterion
from app.knowledge_base.questions import CriterionQuestion
from app.models.contract import CriterionRef, ProjectProfile, Question, QuestionSet

MAX_QUESTIONS = 10
MIN_POINTS = 3
KIND_POINTS = {"muss": 3, "soll": 1, "bewertung": 0}
LEVER_POINTS = 2

SKIP_REASON = "Keine Rückfrage würde die Einstufung eines Programms ändern."


@dataclass
class _Candidate:
    question: CriterionQuestion
    points: int = 0
    affects: list[CriterionRef] = field(default_factory=list)
    instrument_names: list[str] = field(default_factory=list)


def build_questions(
    profile: ProjectProfile,
    candidates: Iterable[FlatInstrument],
    index: dict[str, CriterionQuestion],
    max_questions: int = MAX_QUESTIONS,
) -> QuestionSet:
    """`candidates` are the instruments that survived the pre-filter."""
    scored: dict[str, _Candidate] = {}
    for item in candidates:
        for scoped in item.criteria():
            question = index.get(scoped.criterion.id)
            if question is None or not _is_open(profile, scoped, question):
                continue
            candidate = scored.setdefault(question.criterion_id, _Candidate(question))
            _add(candidate, item, scoped)
    ranked = sorted(
        (c for c in scored.values() if c.points >= MIN_POINTS), key=lambda c: -c.points
    )[:max_questions]
    return QuestionSet(
        questions=[_to_question(c) for c in ranked],
        skip_reason=None if ranked else SKIP_REASON,
    )


def _is_open(profile: ProjectProfile, scoped: ScopedCriterion, question: CriterionQuestion) -> bool:
    """Not answered yet, and the profile cannot decide the criterion on its own."""
    if known(profile, question.profile_field) is not None:
        return False
    fields = scoped.criterion.profile_fields
    return not fields or any(known(profile, name) is None for name in fields)


def _add(candidate: _Candidate, item: FlatInstrument, scoped: ScopedCriterion) -> None:
    criterion = scoped.criterion
    candidate.points += KIND_POINTS[criterion.kind]
    if item.levers_for(criterion.id):
        candidate.points += LEVER_POINTS
    instrument_id = item.instrument.id if scoped.scope == "instrument" else None
    ref = CriterionRef(
        program_id=item.program.id, instrument_id=instrument_id, criterion_id=criterion.id
    )
    if ref not in candidate.affects:
        candidate.affects.append(ref)
    if item.instrument.name not in candidate.instrument_names:
        candidate.instrument_names.append(item.instrument.name)


def _to_question(candidate: _Candidate) -> Question:
    question = candidate.question
    return Question(
        id=f"q_{question.criterion_id}",
        profile_field=question.profile_field,
        text=question.text,
        why=f"Entscheidet über: {', '.join(candidate.instrument_names)}.",
        input="auswahl",
        unit=None,
        options=list(question.options),
        affects=candidate.affects,
        prefill=None,
    )
