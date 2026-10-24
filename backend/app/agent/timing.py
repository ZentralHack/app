"""Conditions on timing that the user can still meet, pure code.

"Das Gesuch ist vor Baubeginn eingereicht" cannot be proven before the application, so the
matching step calls it `unbekannt`. But if the project starts in the future, the user can still
meet it: that is `annahme` (shown as "erfüllbar") with what to do, not an open point.

Applies to `zeit` criteria that need `projektstart` and say "vor <event>". Only a project start
in the past, or the answer that work has already begun, leaves the matching result standing.
"""

import re
from collections.abc import Callable
from datetime import date

from app.agent.deadlines import project_start
from app.agent.profile_values import known
from app.knowledge_base.questions import RUECKFRAGE
from app.models.contract import CriterionResult, ProjectProfile
from app.models.program import Criterion

# Event named in the criterion → what the user has to do before it.
_EVENTS: tuple[tuple[str, str], ...] = (
    ("Installationsbeginn", "Gesuch vor Installationsbeginn einreichen."),
    ("Baubeginn", "Gesuch vor Baubeginn einreichen."),
    ("Projektbeginn", "Gesuch vor Projektstart einreichen."),
    ("Projektstart", "Gesuch vor Projektstart einreichen."),
    ("der Durchführung", "Antrag vor der Durchführung einreichen."),
    ("dem Zuschlagsentscheid", "Erst nach dem Zuschlagsentscheid mit der Umsetzung beginnen."),
)
_BEFORE = re.compile(r"\bvor (" + "|".join(re.escape(e) for e, _ in _EVENTS) + r")\b")
# Answers to the criterion's own question that say: not started yet.
_NOT_STARTED = re.compile(r"^Nein\b")


def before_start_action(criterion: Criterion) -> str | None:
    """What to do for a "before the project starts" criterion, or None for other criteria."""
    if criterion.about != "zeit" or "projektstart" not in criterion.profile_fields:
        return None
    match = _BEFORE.search(criterion.text)
    return dict(_EVENTS)[match.group(1)] if match else None


def apply_timing(
    criterion: Criterion,
    result: CriterionResult,
    profile: ProjectProfile,
    today: date,
    cost_year_rule: Callable[[int], date] | None = None,
) -> CriterionResult:
    """`cost_year_rule`: the instrument's claim deadline per cost year (deadlines.py), if its
    costs are claimed after the year they arise in (LIB)."""
    if cost_year_rule is not None and _is_cost_year(criterion):
        return _apply_cost_year(criterion, result, profile, today, cost_year_rule)
    action = before_start_action(criterion)
    if action is None:
        return result
    answer_field = f"{RUECKFRAGE}{criterion.id}"
    answer = known(profile, answer_field)
    start = project_start(profile)
    not_started = isinstance(answer, str) and _NOT_STARTED.match(answer)
    if answer is not None and not not_started:
        return result  # work has begun, or "Weiss nicht": the matching result stands
    if start is not None and start <= today:
        # Never "erfüllbar" once the start is reached, even if the answer says not started.
        if result.state == "nicht_erfuellt":
            return result
        reason = f"Projektstart {start:%m/%Y} liegt vor dem Gesuch: {_too_late(action)}"
        return _update(result, "unbekannt", reason, [])
    if not_started:
        reason = f"Laut Ihrer Antwort hat das Projekt noch nicht begonnen. {action}"
        return _update(result, "annahme", reason, [answer_field])
    if start is not None:
        reason = f"Projekt startet {start:%m/%Y}. {action}"
        return _update(result, "annahme", reason, ["projektstart"])
    return result


def _too_late(action: str) -> str:
    """'Gesuch vor Baubeginn einreichen.' → 'Gesuch muss vor Baubeginn eingereicht werden.'"""
    match = re.match(r"^(Gesuch|Antrag) (vor .+) einreichen\.$", action)
    if match is None:
        return action
    return f"{match.group(1)} muss {match.group(2)} eingereicht werden."


# Answers to the cost-year question that say: the costs are still to come.
_COSTS_AHEAD = ("Fallen erst an", "Laufend")


def _is_cost_year(criterion: Criterion) -> bool:
    return criterion.about == "zeit" and "Bemessungsjahr" in criterion.text


def _apply_cost_year(
    criterion: Criterion,
    result: CriterionResult,
    profile: ProjectProfile,
    today: date,
    claim_deadline: Callable[[int], date],
) -> CriterionResult:
    """ "Costs are in the accounts of the assessment year" cannot hold for costs still to come,
    but they will: they count in the year they arise and are claimed two years later
    (LIB Handbuch N 35-39). That is fulfillable, not a failure."""
    if result.state == "erfuellt":
        return result
    answer_field = f"{RUECKFRAGE}{criterion.id}"
    answer = known(profile, answer_field)
    start = project_start(profile)
    if isinstance(answer, str) and answer.startswith(_COSTS_AHEAD):
        evidence = [answer_field]
    elif answer is None and start is not None and start > today:
        evidence = ["projektstart"]
    else:
        return result
    if start is not None and start > today:
        due = claim_deadline(start.year)
        reason = (
            f"Die Kosten fallen ab {start:%m/%Y} an und zählen im Geschäftsjahr {start.year}. "
            f"Gesuch für das Beitragsjahr {due.year} bis {due:%d.%m.%Y}."
        )
    else:
        reason = (
            "Die Kosten fallen erst an. Sie zählen im Geschäftsjahr, in dem sie anfallen, "
            "und werden zwei Jahre später im Gesuch geltend gemacht."
        )
    return _update(result, "annahme", reason, evidence)


def _update(
    result: CriterionResult, state: str, reason: str, evidence: list[str]
) -> CriterionResult:
    return result.model_copy(update={"state": state, "reason": reason, "evidence": evidence})
