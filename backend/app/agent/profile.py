"""Step 1 (profile): free text → structured profile. One LLM call (small model), then
code checks: quotes must occur in the text, values must fit the field types and the
knowledge base enums. Too vague input asks what the money is for."""

import logging
from typing import Any, Literal

from pydantic import create_model

from app.agent.normalize import CLARIFICATION, is_too_vague, normalize_profile
from app.agent.text import occurs, squash
from app.knowledge_base.profile_fields import FIELD_TYPES, field_descriptions
from app.llm.client import LLMClient
from app.llm.prompts import render
from app.llm.schema import LLMOutput
from app.models.contract import ProfileField, ProfileRequest, ProfileResponse, ProjectProfile

log = logging.getLogger(__name__)


class ExtractedField(LLMOutput):
    value: str | int | float | bool | list[str] | None
    status: Literal["angegeben", "annahme", "fehlt"]
    quote: str | None
    note: str | None


# One required property per profile field, so the model has to answer every field.
ExtractedFields = create_model(
    "ExtractedFields",
    __base__=LLMOutput,
    **{name: (ExtractedField, ...) for name in FIELD_TYPES},
)


class ProfileExtraction(LLMOutput):
    summary: str
    purpose_quote: str | None  # the words saying what the money is for
    fields: ExtractedFields  # type: ignore[valid-type]


def _field_list() -> str:
    lines = []
    for name, description in field_descriptions().items():
        allowed = FIELD_TYPES[name].allowed
        suffix = f" Erlaubte Werte: {', '.join(sorted(allowed))}." if allowed else ""
        lines.append(f"- `{name}`: {description}.{suffix}")
    return "\n".join(lines)


def _user_message(req: ProfileRequest) -> str:
    form = {
        "Gemeinde": req.gemeinde,
        "Mitarbeitende": req.mitarbeitende,
        "Budget CHF": req.budget_chf,
    }
    form_lines = [f"- {k}: {v}" for k, v in form.items() if v is not None]
    parts = ["Projektbeschreibung:", "<<<", req.text, ">>>"]
    if form_lines:
        parts += ["", "Angaben aus dem Formular:", *form_lines]
    return "\n".join(parts)


async def extract_profile(req: ProfileRequest, llm: LLMClient) -> ProfileResponse:
    extraction = await llm.structured(
        task="profile",
        system=render("profile", fields=_field_list()),
        user=_user_message(req),
        output=ProfileExtraction,
        tier="small",
        effort="low",
    )
    profile = build_profile(req, extraction)
    if not _states_purpose(extraction, req.text) or is_too_vague(profile):
        return ProfileResponse(
            status="needs_clarification", profile=None, clarification=CLARIFICATION
        )
    return ProfileResponse(status="ok", profile=profile, clarification=None)


def build_profile(req: ProfileRequest, extraction: ProfileExtraction) -> ProjectProfile:
    """Code checks on the model output. Form fields always win and count as `angegeben`."""
    fields = {
        name: _checked(name, getattr(extraction.fields, name), req.text) for name in FIELD_TYPES
    }
    profile = ProjectProfile(input_text=req.text, summary=extraction.summary, fields=fields)
    return normalize_profile(with_form_fields(profile, req))


def with_form_fields(profile: ProjectProfile, req: ProfileRequest) -> ProjectProfile:
    """The values from the form on page 1 replace whatever the text gave: `angegeben`, origin
    `formular`. Same rule for the live path and the demo replay."""
    form = {
        "standort_gemeinde": req.gemeinde,
        "mitarbeitende": req.mitarbeitende,
        "budget": req.budget_chf,
    }
    fields = dict(profile.fields)
    for name, value in form.items():
        if value is not None:
            fields[name] = ProfileField(
                value=_coerce(name, value),
                status="angegeben",
                origin="formular",
                quote=None,
                note=None,
            )
    return profile.model_copy(update={"fields": fields})


def _states_purpose(extraction: ProfileExtraction, text: str) -> bool:
    """The text names what the money is for, proven by a quote from it."""
    quote = extraction.purpose_quote
    return quote is not None and occurs(quote, squash(text))


def _checked(name: str, field: ExtractedField, text: str) -> ProfileField:
    if field.status == "fehlt" or field.value is None:
        return ProfileField(value=None, status="fehlt", origin=None, quote=None, note=field.note)
    value = _coerce(name, field.value)
    if value is None:
        log.warning("Profilfeld %s: Wert passt nicht zum Feldtyp, verworfen", name)
        return _missing("Wert passte nicht zum Feldtyp und wurde verworfen.")
    status, quote, note = field.status, field.quote, field.note
    if quote is not None and not occurs(quote, squash(text)):
        quote = None
    if status == "angegeben" and quote is None:
        log.info("Profilfeld %s: Zitat nicht im Text, herabgestuft auf annahme", name)
        status, note = "annahme", _join(note, "Nicht wörtlich im Text belegt.")
    return ProfileField(
        value=value, status=status, origin="text" if quote else None, quote=quote, note=note
    )


def _coerce(name: str, value: Any) -> Any | None:
    """The value in the field's type, or None if it cannot be. Enum arrays are left to
    `normalize_profile`, which drops unknown values with a note."""
    field_type = FIELD_TYPES[name]
    if field_type.kind == "enum_list":
        return value if isinstance(value, list) else [value]
    if field_type.kind in ("integer", "number") and isinstance(value, float) and value.is_integer():
        value = int(value)
    return value if field_type.accepts(value) else None


def _missing(note: str) -> ProfileField:
    return ProfileField(value=None, status="fehlt", origin=None, quote=None, note=note)


def _join(*notes: str | None) -> str:
    return " ".join(n for n in notes if n)
