"""Deadline logic, pure code. `today` is always a parameter so tests can pin it."""

import re
from collections.abc import Callable
from datetime import date

from app.agent.profile_values import known
from app.knowledge_base.flat import FlatInstrument
from app.models.contract import Deadline, ProjectProfile

FIXED_DATE_TYPES = frozenset({"fester_termin_jaehrlich", "fester_termin", "ausschreibung"})

# LIB: claim years 2026 and 2027 are both due on 31 January 2027 (Handbuch N 165).
LIB_FIRST_DEADLINE = date(2027, 1, 31)

_MONTH = re.compile(r"^(\d{4})-(\d{2})(?:-(\d{2}))?$")


def lib_claim_deadline(cost_year: int) -> date:
    """LIB is assessed on the financial year two years before the claim year: costs of
    year X are claimed in year X+2, due 31 January X+2 (Handbuch N 35-39)."""
    return max(date(cost_year + 2, 1, 31), LIB_FIRST_DEADLINE)


# Instruments whose deadline depends on the year the project costs arise.
COST_YEAR_DEADLINES: dict[str, Callable[[int], date]] = {"lib:lib-beitrag": lib_claim_deadline}


def project_start(profile: ProjectProfile) -> date | None:
    """`projektstart` as ISO date or month 'YYYY-MM' (first of the month)."""
    value = known(profile, "projektstart")
    match = _MONTH.match(value) if isinstance(value, str) else None
    if match is None:
        return None
    year, month, day = match.groups()
    return date(int(year), int(month), int(day or 1))


def next_deadline(item: FlatInstrument, profile: ProjectProfile, today: date) -> date | None:
    """The next date by which something must be submitted, or None if there is none."""
    spec = item.instrument.timing.deadline
    start = project_start(profile)
    cost_year_rule = COST_YEAR_DEADLINES.get(item.key)
    if cost_year_rule and start:
        # Costs of later project years can still be claimed once the first deadline passed.
        return max(cost_year_rule(start.year), _next_january_31(today))
    if spec.type in FIXED_DATE_TYPES:
        return min((d for d in spec.next_dates if d >= today), default=None)
    if spec.type == "vor_projektstart":
        return start
    return None


def _next_january_31(today: date) -> date:
    this_year = date(today.year, 1, 31)
    return this_year if today <= this_year else date(today.year + 1, 1, 31)


def deadline(item: FlatInstrument, profile: ProjectProfile, today: date) -> Deadline:
    spec = item.instrument.timing.deadline
    due = next_deadline(item, profile, today)
    return Deadline(type=spec.type, rule=cost_year_note(item, due) or spec.rule, next_date=due)


def cost_year_note(item: FlatInstrument, due: date | None) -> str | None:
    """For deadlines that follow the cost year: which claim year the date is and which
    financial year it is assessed on, so a date two years ahead does not look wrong."""
    if item.key not in COST_YEAR_DEADLINES or due is None:
        return None
    return f"Beitragsjahr {due.year}, bemessen auf Ihre Kosten im Geschäftsjahr {due.year - 2}."
