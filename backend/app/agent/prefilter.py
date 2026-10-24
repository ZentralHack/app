"""Step 3 (pre-filter), pure code. Drops instruments that certainly do not fit.

Rules run in RULES order; the first that applies gives `Rejected.rule`. Except for
`verfuegbarkeit`, a rule only drops on a known profile value (`angegeben` or `annahme`).
A missing value keeps the instrument. Required partners never drop an instrument
(see knowledge_base/partners.py). Project types are compared with their implied types
(see project_types.py).
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal

from app.agent.profile_values import known, known_set
from app.agent.project_types import with_implied
from app.knowledge_base.flat import FlatInstrument
from app.models.contract import ProjectProfile, Rejected

type Check = Callable[[ProjectProfile, FlatInstrument], str | None]
type RejectRule = Literal[
    "verfuegbarkeit",
    "kanton",
    "gesuchsteller",
    "vorhaben",
    "branche",
    "mitarbeitende",
    "unternehmensalter",
]


@dataclass(frozen=True)
class PrefilterResult:
    kept: list[FlatInstrument]
    rejected: list[Rejected]


AVAILABILITY_TEXT = {
    "geplant": "Das Instrument ist angekündigt, aber noch nicht beantragbar.",
    "runde_geschlossen": "Die aktuelle Ausschreibungsrunde ist geschlossen.",
    "eingestellt": "Das Instrument wird nicht mehr angeboten.",
}


def _availability(_: ProjectProfile, item: FlatInstrument) -> str | None:
    availability = item.instrument.availability
    if availability.status == "aktiv":
        return None
    reason = AVAILABILITY_TEXT[availability.status]
    if availability.next_round:
        reason += f" Nächste Runde ab {availability.next_round:%d.%m.%Y}."
    return reason


def _location(profile: ProjectProfile, item: FlatInstrument) -> str | None:
    """Canton first, then municipality. Both are reported under the rule `kanton`, the
    contract's location rule."""
    cantons = item.program.scope.cantons
    canton = known(profile, "standort_kanton")
    if cantons and canton is not None and canton not in cantons:
        return f"Gilt nur im Kanton {', '.join(cantons)}; Ihr Standort liegt im Kanton {canton}."
    municipalities = item.program.scope.municipalities
    municipality = known(profile, "standort_gemeinde")
    if not municipalities or not isinstance(municipality, str):
        return None
    if _normalised(municipality) in {_normalised(m) for m in municipalities}:
        return None
    return f"Gilt nur in der Gemeinde {', '.join(municipalities)}; Ihr Standort ist {municipality}."


def _normalised(name: str) -> str:
    return " ".join(name.split()).casefold()


def _overlap_check(
    profile_field: str,
    filter_field: str,
    reason: str,
    expand: Callable[[set[str]], set[str]] = lambda values: values,
) -> Check:
    """Drop if the filter list is restricted and the known profile values miss it entirely.
    An empty filter list means: no restriction. `expand` adds implied values first."""

    def check(profile: ProjectProfile, item: FlatInstrument) -> str | None:
        allowed = getattr(item.instrument.filter, filter_field)
        values = known_set(profile, profile_field)
        if not allowed or values is None or expand(values) & set(allowed):
            return None
        return reason

    return check


def _employees(profile: ProjectProfile, item: FlatInstrument) -> str | None:
    count = known(profile, "mitarbeitende")
    low, high = item.instrument.filter.employees_min, item.instrument.filter.employees_max
    if count is None or ((low is None or count >= low) and (high is None or count <= high)):
        return None
    if low is not None and high is not None:
        allowed = f"{low} bis {high}"
    else:
        allowed = f"mindestens {low}" if low is not None else f"höchstens {high}"
    return f"Gilt für Unternehmen mit {allowed} Mitarbeitenden; Sie haben {count}."


def _company_age(profile: ProjectProfile, item: FlatInstrument) -> str | None:
    age = known(profile, "unternehmensalter")
    limit = item.instrument.filter.company_age_years_max
    if age is None or limit is None or age <= limit:
        return None
    return f"Gilt nur für Unternehmen bis {limit} Jahre; Ihr Unternehmen ist {age} Jahre alt."


RULES: tuple[tuple[RejectRule, Check], ...] = (
    ("verfuegbarkeit", _availability),
    ("kanton", _location),
    (
        "gesuchsteller",
        _overlap_check(
            "applicant_type",
            "applicant_types",
            "Ihre Organisationsform gehört nicht zu den zugelassenen Gesuchstellern.",
        ),
    ),
    (
        "vorhaben",
        _overlap_check(
            "art_des_vorhabens",
            "project_types",
            "Das Instrument fördert eine andere Art von Vorhaben.",
            with_implied,
        ),
    ),
    (
        "branche",
        _overlap_check("branche", "sectors", "Das Instrument ist auf andere Branchen beschränkt."),
    ),
    ("mitarbeitende", _employees),
    ("unternehmensalter", _company_age),
)


def prefilter(profile: ProjectProfile, instruments: Iterable[FlatInstrument]) -> PrefilterResult:
    kept: list[FlatInstrument] = []
    rejected: list[Rejected] = []
    for item in instruments:
        rejection = _first_rejection(profile, item)
        if rejection is None:
            kept.append(item)
        else:
            rejected.append(rejection)
    return PrefilterResult(kept, rejected)


def _first_rejection(profile: ProjectProfile, item: FlatInstrument) -> Rejected | None:
    for rule, check in RULES:
        reason = check(profile, item)
        if reason is None:
            continue
        availability = item.instrument.availability if rule == "verfuegbarkeit" else None
        return Rejected(
            program_id=item.program.id,
            instrument_id=item.instrument.id,
            program_name=item.program.name,
            instrument_name=item.instrument.name,
            reason=reason,
            rule=rule,
            availability_status=availability.status if availability else None,
            next_round=availability.next_round if availability else None,
        )
    return None
