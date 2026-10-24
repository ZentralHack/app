"""Conditions on timing that the user can still meet, pure code.

"Das Gesuch ist vor Baubeginn eingereicht" cannot be proven before the application, so the
matching step calls it `unbekannt`. But if the project starts in the future, the user can still
meet it: that is `annahme` (shown as "erfüllbar") with what to do, not an open point.

Applies to `zeit` criteria that need `projektstart` and say "vor <event>". Only a project start
in the past, or the answer that work has already begun, leaves the matching result standing.
"""

import re
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
    criterion: Criterion, result: CriterionResult, profile: ProjectProfile, today: date
) -> CriterionResult:
    action = before_start_action(criterion)
    if action is None:
        return result
    answer_field = f"{RUECKFRAGE}{criterion.id}"
    answer = known(profile, answer_field)
    start = project_start(profile)
    if isinstance(answer, str) and _NOT_STARTED.match(answer):
        reason = f"Laut Ihrer Antwort hat das Projekt noch nicht begonnen. {action}"
        return _update(result, "annahme", reason, [answer_field])
    if answer is not None:
        return result  # work has begun, or "Weiss nicht": the matching result stands
    if start is not None and start > today:
        reason = f"Projekt startet {start:%m/%Y}. {action}"
        return _update(result, "annahme", reason, ["projektstart"])
    if start is not None and result.state in ("erfuellt", "annahme"):
        reason = (
            f"Der Projektstart {start:%m/%Y} ist erreicht. "
            "Ob das Gesuch vorher eingereicht wurde, ist offen."
        )
        return _update(result, "unbekannt", reason, [])
    return result


def _update(
    result: CriterionResult, state: str, reason: str, evidence: list[str]
) -> CriterionResult:
    return result.model_copy(update={"state": state, "reason": reason, "evidence": evidence})
