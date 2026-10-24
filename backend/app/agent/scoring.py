"""Step 5 (scoring and ranking), pure code and deterministic.

Fit level per instrument, first matching rule wins:
1. a `muss` criterion is `nicht_erfuellt` and no lever targets it → passt_nicht
2. an exclusion or negative example applies                      → passt_nicht
3. a `muss` criterion is `nicht_erfuellt`, but a lever targets it → passt_mit_anpassung
4. more than a third of the `muss` criteria are `unbekannt`        → passt_mit_anpassung
5. otherwise                                                       → passt_gut

Every `unbekannt` criterion gets an `infos_fehlen` gap. So "passt gut" never hides an
unknown `muss` criterion (stricter than the backend flow, which only counts the share).

Ranking over all fitting instruments, first key wins:
1. money before advice: `instrument_type` "beratung" goes into its own block after all others
2. fit level
3. floor: more than two thirds of the `muss` criteria unknown sorts after the rest of its level
4. share of `muss` met (`annahme` counts half), nearest deadline, entitlement
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from typing import Literal

from app.knowledge_base.flat import FlatInstrument
from app.knowledge_base.partners import partner_lever
from app.models.contract import CriterionResult, Gap, SourceLink
from app.models.program import EntitlementType

type Fit = Literal["passt_gut", "passt_mit_anpassung", "passt_nicht"]

UNKNOWN_MUSS_LIMIT = Fraction(1, 3)
MOSTLY_UNKNOWN_LIMIT = Fraction(2, 3)
ASSUMED_WEIGHT = Fraction(1, 2)
ADVISORY_TYPES = frozenset({"beratung"})
FIT_ORDER: dict[Fit, int] = {"passt_gut": 0, "passt_mit_anpassung": 1, "passt_nicht": 2}
ENTITLEMENT_ORDER: dict[EntitlementType, int] = {
    "rechtsanspruch_im_budget": 0,
    "kein_rechtsanspruch": 1,
    "wettbewerb": 2,
}


@dataclass(frozen=True)
class Score:
    fit: Fit
    gaps: list[Gap]
    muss_met_share: Fraction


def score(
    item: FlatInstrument,
    criteria: list[CriterionResult],
    exclusion_hit: bool,
    preferred_levers: Sequence[str] = (),
) -> Score:
    """`preferred_levers`: lever texts the matching step picked, used first if they apply."""
    muss = _applicable_muss(criteria)
    failed = [c for c in muss if c.state == "nicht_erfuellt"]
    unknown_muss = [c for c in muss if c.state == "unbekannt"]
    levers = {c.criterion_id: _lever(item, c, preferred_levers) for c in criteria}

    if any(levers[c.criterion_id] is None for c in failed) or exclusion_hit:
        fit: Fit = "passt_nicht"
    elif failed or (muss and Fraction(len(unknown_muss), len(muss)) > UNKNOWN_MUSS_LIMIT):
        fit = "passt_mit_anpassung"
    else:
        fit = "passt_gut"

    gaps = [
        _gap(item, "anpassung", c, levers[c.criterion_id])
        for c in failed
        if levers[c.criterion_id] is not None
    ] + [
        _gap(item, "infos_fehlen", c, levers[c.criterion_id])
        for c in criteria
        if c.state == "unbekannt"
    ]
    return Score(fit, gaps, muss_met_share(criteria))


def _applicable_muss(criteria: Sequence[CriterionResult]) -> list[CriterionResult]:
    return [c for c in criteria if c.kind == "muss" and c.state != "nicht_anwendbar"]


def muss_met_share(criteria: Sequence[CriterionResult]) -> Fraction:
    """Share of applicable `muss` criteria that are met, `annahme` counting half; 0 without any."""
    muss = _applicable_muss(criteria)
    if not muss:
        return Fraction(0)
    met = sum(
        Fraction(1) if c.state == "erfuellt" else ASSUMED_WEIGHT if c.state == "annahme" else 0
        for c in muss
    )
    return met / len(muss)


def mostly_unknown(criteria: Sequence[CriterionResult]) -> bool:
    """Too little is known to say much: more than two thirds of the `muss` criteria unknown."""
    muss = _applicable_muss(criteria)
    unknown = sum(c.state == "unbekannt" for c in muss)
    return bool(muss) and Fraction(unknown, len(muss)) > MOSTLY_UNKNOWN_LIMIT


def is_advisory(instrument_type: str) -> bool:
    """Advice instead of money; shown as "Begleitende Angebote" below the funding."""
    return instrument_type in ADVISORY_TYPES


@dataclass(frozen=True)
class _Lever:
    text: str
    source: SourceLink | None


def _lever(
    item: FlatInstrument, criterion: CriterionResult, preferred: Sequence[str]
) -> _Lever | None:
    """The lever text that could change this criterion: fixed for partner criteria,
    otherwise the first lever in the knowledge base. Never invented."""
    if criterion.scope == "filter":
        text = partner_lever(criterion.criterion_id)
        return _Lever(text, criterion.source) if text else None
    levers = sorted(
        item.levers_for(criterion.criterion_id), key=lambda lever: lever.text not in preferred
    )
    if not levers:
        return None
    return _Lever(levers[0].text, item.source_link(levers[0].source) or criterion.source)


def _gap(
    item: FlatInstrument,
    gap_type: Literal["anpassung", "infos_fehlen"],
    criterion: CriterionResult,
    lever: _Lever | None,
) -> Gap:
    return Gap(
        type=gap_type,
        criterion_ids=[criterion.criterion_id],
        lever=lever.text if lever else None,
        hint=None,
        source=lever.source if lever else criterion.source,
    )


@dataclass(frozen=True)
class RankEntry:
    key: str
    fit: Fit
    muss_met_share: Fraction
    next_deadline: date | None
    entitlement: EntitlementType
    advisory: bool = False
    mostly_unknown: bool = False


def assign_ranks(entries: Sequence[RankEntry]) -> dict[str, int | None]:
    """1-based rank over all fitting instruments; `passt_nicht` gets no rank.
    Order: money before advice, fit level, floor for mostly unknown, share of `muss` met,
    nearest deadline, entitlement."""
    ordered = sorted(
        entries,
        key=lambda e: (
            e.advisory,
            FIT_ORDER[e.fit],
            e.mostly_unknown,
            -e.muss_met_share,
            e.next_deadline or date.max,
            ENTITLEMENT_ORDER[e.entitlement],
        ),
    )
    fitting = [e for e in ordered if e.fit != "passt_nicht"]
    ranks: dict[str, int | None] = {e.key: None for e in entries}
    ranks.update({e.key: position for position, e in enumerate(fitting, start=1)})
    return ranks
