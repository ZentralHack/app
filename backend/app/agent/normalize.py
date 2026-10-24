"""Code checks on the extracted profile, before the pre-filter runs.

The enum fields must only hold values the knowledge base knows, because the pre-filter
compares them directly with `instrument.filter`.
"""

import logging

from app.agent.errors import InvalidInputError
from app.agent.profile_values import known
from app.knowledge_base.enums import PROFILE_ENUMS
from app.knowledge_base.profile_fields import FIELD_TYPES
from app.knowledge_base.questions import RUECKFRAGE, CriterionQuestion
from app.models.contract import Clarification, ProfileField, ProjectProfile

log = logging.getLogger(__name__)

# `partner: []` means "no partner involved", which is a known answer.
EMPTY_IS_KNOWN = frozenset({"partner"})

CLARIFICATION = Clarification(
    question="Wofür brauchen Sie die Förderung?",
    options=["Entwicklung", "Energie", "Export", "Gründung", "Anderes"],
)


def normalize_profile(profile: ProjectProfile) -> ProjectProfile:
    """Drop enum values the knowledge base does not know. A field left empty becomes `fehlt`."""
    fields = dict(profile.fields)
    for name, allowed in PROFILE_ENUMS.items():
        field = fields.get(name)
        if field is None or field.status == "fehlt":
            continue
        fields[name] = _normalize_enum_field(name, field, allowed)
    return profile.model_copy(update={"fields": fields})


def _normalize_enum_field(name: str, field: ProfileField, allowed: frozenset[str]) -> ProfileField:
    raw = field.value if isinstance(field.value, list) else [field.value]
    values = [str(v) for v in raw]
    kept = list(dict.fromkeys(v for v in values if v in allowed))
    dropped = [v for v in values if v not in allowed]
    if not dropped and (kept or name in EMPTY_IS_KNOWN):
        return field if field.value == kept else field.model_copy(update={"value": kept})
    if dropped:
        log.warning("Profilfeld %s: unbekannte Werte verworfen: %s", name, dropped)
    note = _join_notes(field.note, _dropped_note(dropped))
    if kept:
        return field.model_copy(update={"value": kept, "note": note})
    return field.model_copy(update={"value": None, "status": "fehlt", "note": note})


def _dropped_note(dropped: list[str]) -> str:
    if not dropped:
        return "Kein Wert erkannt."
    return f"Nicht erkannte Werte verworfen: {', '.join(dropped)}."


def _join_notes(*notes: str | None) -> str:
    return " ".join(n for n in notes if n)


def is_too_vague(profile: ProjectProfile) -> bool:
    """Neither a project type nor a description: ask what the money is for."""
    description = known(profile, "vorhaben_beschreibung")
    has_description = isinstance(description, str) and bool(description.strip())
    return not known(profile, "art_des_vorhabens") and not has_description


def validate_profile(
    profile: ProjectProfile, criterion_questions: dict[str, CriterionQuestion]
) -> None:
    """Checks a profile sent by a client (e.g. after corrections on Screen 2). Unlike
    `normalize_profile` for model output, nothing is dropped silently: any value the
    knowledge base does not know is an error."""
    problems = []
    for name, field in profile.fields.items():
        if (field.status == "fehlt") != (field.value is None):
            problems.append(f"{name}: value ist genau dann null, wenn status 'fehlt' ist")
            continue
        field_type = FIELD_TYPES.get(name)
        question = criterion_questions.get(name.removeprefix(RUECKFRAGE))
        if field_type is not None:
            if field.value is not None and not field_type.accepts(field.value):
                problems.append(f"{name}: Wert {field.value!r} ist nicht erlaubt")
        elif name.startswith(RUECKFRAGE) and question is not None:
            if field.value is not None and field.value not in question.options:
                problems.append(f"{name}: Antwort {field.value!r} ist nicht erlaubt")
        else:
            problems.append(f"{name}: unbekanntes Profilfeld")
    if problems:
        raise InvalidInputError("Ungültiges Profil: " + "; ".join(problems))
