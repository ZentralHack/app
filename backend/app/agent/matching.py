"""Step 4 (matching): one LLM call per instrument, then code post-checks.

Post-checks on every answer:
1. unknown criterion ids are dropped, duplicates keep the first, missing ones become
   `unbekannt`
2. evidence rule: `erfuellt` or `nicht_erfuellt` needs known profile fields and a quote that
   occurs in the profile, otherwise `unbekannt`; `erfuellt` resting only on assumed fields
   becomes `annahme`
3. `nicht_anwendbar` only for criteria with `applies_if`
4. exclusion hits and lever ids must exist and exclusion hits need a quote
Sources always come from the knowledge base, never from the model.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

from app.agent.text import occurs, squash
from app.knowledge_base.flat import FlatInstrument, ScopedCriterion
from app.llm.client import LLMClient
from app.llm.prompts import load_prompt
from app.llm.schema import LLMOutput
from app.models.contract import CriterionResult, ProjectProfile

log = logging.getLogger(__name__)

NOT_CHECKED = "Nicht geprüft, es fehlen Angaben."
NO_EVIDENCE = "Kein Beleg im Profil."


class CriterionCheck(LLMOutput):
    criterion_id: str
    state: Literal["erfuellt", "annahme", "unbekannt", "nicht_erfuellt", "nicht_anwendbar"]
    reason: str
    evidence_fields: list[str]
    quotes: list[str]


class ExclusionHit(LLMOutput):
    exclusion_id: str
    quotes: list[str]


class MatchingOutput(LLMOutput):
    criteria: list[CriterionCheck]
    exclusion_hits: list[ExclusionHit]
    lever_ids: list[str]


@dataclass(frozen=True)
class InstrumentCheck:
    criteria: list[CriterionResult]
    exclusion_hits: list[str]
    lever_texts: list[str]
    downgrades: int


async def check_instrument(
    item: FlatInstrument, profile: ProjectProfile, llm: LLMClient
) -> InstrumentCheck:
    output = await llm.structured(
        task="matching",
        system=load_prompt("matching"),
        user=matching_input(item, profile),
        output=MatchingOutput,
        tier="main",
        effort="low",
    )
    return post_check(item, profile, output)


def _exclusions(item: FlatInstrument) -> dict[str, str]:
    """Exclusions and negative examples by id, as shown to the model."""
    texts = [e.text for e in (*item.program.general_exclusions, *item.instrument.exclusions)]
    texts += [
        f"{e.name}: {example}"
        for e in item.instrument.eligible_items
        for example in e.examples_negative
    ]
    return {f"ausschluss_{i}": text for i, text in enumerate(texts, start=1)}


def _levers(item: FlatInstrument) -> dict[str, str]:
    return {f"hebel_{i}": lever.text for i, lever in enumerate(item.instrument.levers, start=1)}


def matching_input(item: FlatInstrument, profile: ProjectProfile) -> str:
    instrument = {
        "programm": item.program.name,
        "instrument": item.instrument.name,
        "kriterien": [
            {
                "criterion_id": s.criterion.id,
                "art": s.criterion.kind,
                "text": s.criterion.text,
                "applies_if": s.criterion.applies_if,
                "hinweis": s.criterion.notes,
                "profilfelder": s.criterion.profile_fields,
            }
            for s in item.criteria()
        ],
        "foerderbare_taetigkeiten": [
            {"name": e.name, "definition": e.definition, "beispiele": e.examples_positive}
            for e in item.instrument.eligible_items
        ],
        "ausschluesse": _exclusions(item),
        "hebel": _levers(item),
    }
    fields = {
        name: {"wert": f.value, "status": f.status, "zitat": f.quote, "hinweis": f.note}
        for name, f in profile.fields.items()
        if f.status != "fehlt"
    }
    missing = sorted(name for name, f in profile.fields.items() if f.status == "fehlt")
    data = {
        "vorhaben": {"text": profile.input_text, "zusammenfassung": profile.summary},
        "profil": fields,
        "fehlende_felder": missing,
        "instrument": instrument,
    }
    return json.dumps(data, ensure_ascii=False, indent=1)


def post_check(
    item: FlatInstrument, profile: ProjectProfile, output: MatchingOutput
) -> InstrumentCheck:
    haystack = _haystack(profile)
    by_id: dict[str, CriterionCheck] = {}
    known_ids = {s.criterion.id for s in item.criteria()}
    for check in output.criteria:
        if check.criterion_id not in known_ids:
            log.warning("%s: unbekanntes Kriterium '%s' verworfen", item.key, check.criterion_id)
        elif check.criterion_id in by_id:
            log.warning("%s: Kriterium '%s' doppelt, erstes gilt", item.key, check.criterion_id)
        else:
            by_id[check.criterion_id] = check

    results, downgrades = [], 0
    for scoped in item.criteria():
        check = by_id.get(scoped.criterion.id)
        result, downgraded = _result(item, scoped, check, profile, haystack)
        results.append(result)
        downgrades += downgraded
    if downgrades:
        log.info("%s: %d Herabstufungen durch die Evidenz-Regel", item.key, downgrades)

    exclusions = _exclusions(item)
    hits = []
    for hit in output.exclusion_hits:
        if hit.exclusion_id in exclusions and any(occurs(q, haystack) for q in hit.quotes):
            hits.append(exclusions[hit.exclusion_id])
        else:
            log.warning("%s: Ausschluss '%s' ohne Beleg verworfen", item.key, hit.exclusion_id)
    levers = _levers(item)
    lever_texts = [levers[i] for i in dict.fromkeys(output.lever_ids) if i in levers]
    return InstrumentCheck(results, hits, lever_texts, downgrades)


def _result(
    item: FlatInstrument,
    scoped: ScopedCriterion,
    check: CriterionCheck | None,
    profile: ProjectProfile,
    haystack: str,
) -> tuple[CriterionResult, bool]:
    criterion = scoped.criterion
    state, reason, evidence = "unbekannt", NOT_CHECKED, []
    downgraded = False
    if check is not None:
        state, reason = check.state, check.reason
        evidence = [f for f in dict.fromkeys(check.evidence_fields) if _known(profile, f)]
        if state in ("erfuellt", "nicht_erfuellt") and not (
            evidence and any(occurs(q, haystack) for q in check.quotes)
        ):
            state, reason, evidence, downgraded = "unbekannt", f"{reason} ({NO_EVIDENCE})", [], True
        elif state == "erfuellt" and all(profile.fields[f].status == "annahme" for f in evidence):
            state, downgraded = "annahme", True
        elif state == "nicht_anwendbar" and not criterion.applies_if:
            state, downgraded = "unbekannt", True
    return (
        CriterionResult(
            criterion_id=criterion.id,
            scope=scoped.scope,
            text=criterion.text,
            kind=criterion.kind,
            state=state,
            reason=reason,
            evidence=evidence,
            profile_fields=criterion.profile_fields,
            source=item.criterion_source(criterion.source),
        ),
        downgraded,
    )


def _known(profile: ProjectProfile, name: str) -> bool:
    field = profile.fields.get(name)
    return field is not None and field.status != "fehlt"


def _haystack(profile: ProjectProfile) -> str:
    """Everything the user said or answered, as one normalised text."""
    parts: list[Any] = [profile.input_text]
    for field in profile.fields.values():
        if field.status == "fehlt":
            continue
        parts += [field.quote, field.note, field.value]
    return squash(" ".join(_text(p) for p in parts if p is not None))


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
