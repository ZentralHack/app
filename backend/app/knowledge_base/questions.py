"""Question index for the questions step (no LLM at runtime).

The reviewed question catalog (knowledge_base/question_catalog.json, one question per
profile field) does not exist yet. Until it does, every question comes from
`criteria[].question`, and the answer is stored as profile field `rueckfrage_<criterion_id>`.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from app.models.program import Program

log = logging.getLogger(__name__)

DONT_KNOW = "Weiss nicht"


@dataclass(frozen=True)
class CriterionQuestion:
    criterion_id: str
    text: str
    options: tuple[str, ...]

    @property
    def profile_field(self) -> str:
        return f"rueckfrage_{self.criterion_id}"


def build_question_index(programs: Iterable[Program]) -> dict[str, CriterionQuestion]:
    """Criterion id → question. "Weiss nicht" is always the last option."""
    index: dict[str, CriterionQuestion] = {}
    for program in programs:
        criteria = [*program.general_criteria]
        for instrument in program.instruments:
            criteria.extend(instrument.criteria)
        for criterion in criteria:
            question = criterion.question
            if question is None:
                continue
            answers = tuple(o for o in question.options if o != DONT_KNOW)
            if not question.text or len(answers) < 2:
                log.warning("%s:%s: Rückfrage ohne Text oder Optionen", program.id, criterion.id)
                continue
            entry = CriterionQuestion(criterion.id, question.text, (*answers, DONT_KNOW))
            known = index.setdefault(criterion.id, entry)
            if known != entry:
                log.warning("%s:%s: abweichende Rückfrage, erste gilt", program.id, criterion.id)
    return index
