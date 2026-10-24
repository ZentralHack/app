"""Stage 1 of the question catalog validation: code checks.

Runs at every server start and in pytest. `fehler` makes the loader drop the entry
(questions then fall back to `criteria[].question`); `warnung` is only reported.
"""

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Literal

from app.knowledge_base.catalog import (
    DONT_KNOW,
    FILTER_PREFIX,
    CatalogEntry,
    Decision,
    RangeRule,
    ValueRule,
    criteria_on_field,
    fingerprint,
)
from app.knowledge_base.enums import PROFILE_ENUMS
from app.knowledge_base.flat import FlatInstrument
from app.knowledge_base.partners import PREFIX as PARTNER_PREFIX
from app.knowledge_base.profile_fields import FIELD_TYPES, MONTH
from app.models.program import Program

MAX_TEXT = 120
MAX_WHY = 160
MAX_OPTIONS = 7
TODAY_BOUND = "heute"
STALE = "veraltet: kb_fingerprint passt nicht mehr"

_DU_FORM = re.compile(r"\b(du|dich|dir|dein|deine|deinem|deinen|deiner|deines)\b", re.IGNORECASE)
_FIELD_NAME = re.compile(r"\b[a-z0-9]+_[a-z0-9_]+\b")


@dataclass(frozen=True)
class Finding:
    field: str
    severity: Literal["fehler", "warnung"]
    message: str


def check_catalog(
    catalog: dict[str, CatalogEntry],
    programs: Sequence[Program],
    instruments: Sequence[FlatInstrument],
) -> list[Finding]:
    findings: list[Finding] = []
    program_names = {n for p in programs for n in (p.name, p.short_name) if n}
    for field, entry in catalog.items():
        problems = [
            *_field_checks(field),
            *_option_checks(field, entry),
            *_text_checks(entry, program_names),
            *_decision_checks(field, entry, instruments),
        ]
        findings += [Finding(field, "fehler", p) for p in problems]
        if field in FIELD_TYPES and entry.kb_fingerprint != fingerprint(instruments, field):
            findings.append(Finding(field, "warnung", STALE))
    findings += _unloaded(catalog, instruments)
    findings += _coverage(catalog, instruments)
    return findings


def _field_checks(field: str) -> Iterator[str]:
    if field not in FIELD_TYPES:
        yield f"unbekanntes Profilfeld '{field}'"


def _option_checks(field: str, entry: CatalogEntry) -> Iterator[str]:
    labels = [o.label for o in entry.options]
    if len(labels) != len(set(labels)):
        yield "Labels doppelt"
    if [o.label for o in entry.options if o.value is None] != [DONT_KNOW]:
        yield f"genau eine Option '{DONT_KNOW}' mit value null nötig, und nur sie mit null"
    answers = [o for o in entry.options if o.value is not None]
    if entry.input == "auswahl":
        if not 2 <= len(answers) <= MAX_OPTIONS:
            yield f"auswahl braucht 2 bis {MAX_OPTIONS} echte Optionen"
        if entry.unit or entry.min is not None or entry.max is not None:
            yield "unit, min und max nur bei zahl"
    else:
        if answers:
            yield f"bei {entry.input} ist '{DONT_KNOW}' die einzige Option"
        if entry.input == "zahl" and (entry.unit is None or entry.min is None or entry.max is None):
            yield "zahl braucht unit, min und max"
    field_type = FIELD_TYPES.get(field)
    if field_type:
        for option in answers:
            if not field_type.accepts(option.value):
                yield f"value {option.value!r} passt nicht zum Typ von '{field}'"


def _text_checks(entry: CatalogEntry, program_names: set[str]) -> Iterator[str]:
    text = entry.text
    if not text.endswith("?"):
        yield "Frage endet nicht mit '?'"
    if len(text) > MAX_TEXT:
        yield f"Frage länger als {MAX_TEXT} Zeichen"
    if len(entry.why) > MAX_WHY:
        yield f"why länger als {MAX_WHY} Zeichen"
    for part in (text, entry.why, *(o.label for o in entry.options)):
        if "ß" in part:
            yield f"'ß' in '{part}'"
        if _DU_FORM.search(part):
            yield f"Du-Form in '{part}'"
        if _FIELD_NAME.search(part):
            yield f"interner Feldname in '{part}'"
        if any(name in part for name in program_names):
            yield f"Programmname in '{part}'"


def _decision_checks(
    field: str, entry: CatalogEntry, instruments: Sequence[FlatInstrument]
) -> Iterator[str]:
    on_field = criteria_on_field(instruments, field)
    refs = [d.criterion for d in entry.decides]
    if len(refs) != len(set(refs)):
        yield "Kriterium mehrfach in decides"
    for decision in entry.decides:
        if not _program_loaded(decision.criterion, instruments):
            continue  # reported as a warning in _unloaded
        if not _exists(decision.criterion, field, on_field):
            yield f"decides: '{decision.criterion}' ist kein Kriterium auf '{field}'"
        if len(decision.states) < 2:
            yield f"decides: '{decision.criterion}' ergibt nur einen Status, entscheidet nichts"
        yield from _rule_checks(entry, decision)
    for item in entry.not_decidable:
        if _program_loaded(item.criterion, instruments) and not _exists(
            item.criterion, field, on_field
        ):
            yield f"not_decidable: '{item.criterion}' ist kein Kriterium auf '{field}'"
    listed = set(refs) | {n.criterion for n in entry.not_decidable}
    for ref, occurrences in on_field.items():
        if ref not in listed and any(s.criterion.kind == "muss" for _, s in occurrences):
            yield f"muss-Kriterium '{ref}' fehlt in decides und not_decidable"


def _program_loaded(ref: str, instruments: Sequence[FlatInstrument]) -> bool:
    owner = ref.partition(":")[0]
    return owner == FILTER_PREFIX or any(item.program.id == owner for item in instruments)


def _unloaded(
    catalog: dict[str, CatalogEntry], instruments: Sequence[FlatInstrument]
) -> list[Finding]:
    """References to programs that are not loaded (missing or invalid file): the entry
    stays usable, the reference is reported."""
    return [
        Finding(field, "warnung", f"Programm von '{ref}' ist nicht geladen")
        for field, entry in catalog.items()
        for ref in [d.criterion for d in entry.decides] + [n.criterion for n in entry.not_decidable]
        if not _program_loaded(ref, instruments)
    ]


def _exists(ref: str, field: str, on_field: dict) -> bool:
    """Known criterion on this field. Partner criteria are generated by code for every
    `required_partners` value, so they count even before an instrument requires them."""
    owner, _, criterion_id = ref.partition(":")
    if owner == FILTER_PREFIX:
        partner = criterion_id.removeprefix(PARTNER_PREFIX)
        return field == "partner" and partner in PROFILE_ENUMS["partner"]
    return ref in on_field


def _rule_checks(entry: CatalogEntry, decision: Decision) -> Iterator[str]:
    values = [o.value for o in entry.options if o.value is not None]
    for rule in decision.map:
        if entry.input == "auswahl":
            if not isinstance(rule, ValueRule) or rule.value not in values:
                yield f"decides: '{decision.criterion}' braucht value einer Option"
        elif not isinstance(rule, RangeRule) or not _valid_range(entry, rule):
            yield f"decides: '{decision.criterion}' braucht gültige min/max-Grenzen"


def _valid_range(entry: CatalogEntry, rule: RangeRule) -> bool:
    def ok(bound: float | str | None) -> bool:
        if bound is None:
            return True
        if entry.input == "zahl":
            return isinstance(bound, int | float)
        return bound == TODAY_BOUND or (isinstance(bound, str) and bool(MONTH.match(bound)))

    return ok(rule.min) and ok(rule.max) and (rule.min is not None or rule.max is not None)


def _coverage(
    catalog: dict[str, CatalogEntry], instruments: Sequence[FlatInstrument]
) -> list[Finding]:
    """Warnings only: the catalog is small on purpose until the generator exists."""
    used = {f for item in instruments for s in item.criteria() for f in s.criterion.profile_fields}
    findings = [
        Finding(field, "warnung", "Waise: kein Kriterium verwendet dieses Feld")
        for field in catalog
        if field not in used
    ]
    for field in sorted(used - set(catalog)):
        without = sorted(
            ref
            for ref, occurrences in criteria_on_field(instruments, field).items()
            if any(s.criterion.question is None for _, s in occurrences)
        )
        if without:
            findings.append(Finding(field, "warnung", f"keine Frage für: {', '.join(without)}"))
    return findings
