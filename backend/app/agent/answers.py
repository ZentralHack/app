"""Apply follow-up answers to the profile, pure code.

Catalog questions write the option's `value` (or the checked number or date) into their
profile field; criterion questions write the chosen label into `rueckfrage_<criterion_id>`.
"Weiss nicht" leaves the field unchanged. Anything else is rejected.
"""

import re

from app.agent.errors import InvalidInputError
from app.knowledge_base.catalog import DONT_KNOW, CatalogEntry
from app.knowledge_base.loader import KnowledgeBase
from app.knowledge_base.profile_fields import FIELD_TYPES, MONTH
from app.knowledge_base.questions import CriterionQuestion
from app.models.contract import Answer, ProfileField, ProjectProfile

RUECKFRAGE = "rueckfrage_"
_NUMBER = re.compile(r"^-?\d+([.,]\d+)?$")


def apply_answers(
    profile: ProjectProfile, answers: list[Answer], kb: KnowledgeBase
) -> ProjectProfile:
    fields = dict(profile.fields)
    seen: set[str] = set()
    for answer in answers:
        if answer.profile_field in seen:
            raise InvalidInputError(f"Mehrere Antworten für '{answer.profile_field}'.")
        seen.add(answer.profile_field)
        if answer.answer == DONT_KNOW:
            continue
        fields[answer.profile_field] = _answer_field(answer, kb)
    return profile.model_copy(update={"fields": fields})


def _answer_field(answer: Answer, kb: KnowledgeBase) -> ProfileField:
    name = answer.profile_field
    entry = kb.catalog.entries.get(name)
    if entry is not None and answer.question_id == f"q_{name}":
        return _field(_catalog_value(name, entry, answer.answer), entry.text, answer.answer)
    criterion_id = name.removeprefix(RUECKFRAGE)
    question = kb.criterion_questions.get(criterion_id)
    if name.startswith(RUECKFRAGE) and question and answer.question_id == f"q_{criterion_id}":
        return _field(_criterion_value(question, answer.answer), question.text, answer.answer)
    raise InvalidInputError(f"Unbekannte Rückfrage '{answer.question_id}' für '{name}'.")


def _catalog_value(name: str, entry: CatalogEntry, text: str) -> object:
    if entry.input == "auswahl":
        option = entry.option(text)
        if option is None:
            raise InvalidInputError(f"'{text}' ist keine Antwortmöglichkeit.")
        return option.value
    if entry.input == "datum":
        if not MONTH.match(text):
            raise InvalidInputError("Bitte ein Datum als JJJJ-MM oder JJJJ-MM-TT angeben.")
        return text
    cleaned = text.replace("'", "").replace(" ", "")
    if not _NUMBER.match(cleaned):
        raise InvalidInputError(f"'{text}' ist keine Zahl.")
    number = float(cleaned.replace(",", "."))
    if (entry.min is not None and number < entry.min) or (
        entry.max is not None and number > entry.max
    ):
        raise InvalidInputError(f"Bitte eine Zahl zwischen {entry.min:g} und {entry.max:g}.")
    if FIELD_TYPES[name].kind == "integer":
        if not number.is_integer():
            raise InvalidInputError("Bitte eine ganze Zahl angeben.")
        return int(number)
    return number


def _criterion_value(question: CriterionQuestion, text: str) -> str:
    if text not in question.options:
        raise InvalidInputError(f"'{text}' ist keine Antwortmöglichkeit.")
    return text


def _field(value: object, question: str, label: str) -> ProfileField:
    return ProfileField(
        value=value,
        status="angegeben",
        origin="rueckfrage",
        quote=None,
        note=f"Rückfrage «{question}»: {label}",
    )
