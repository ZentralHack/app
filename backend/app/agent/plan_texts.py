"""Step 6d (plan texts): the LLM rewrites titles, actions and gap hints of the computed
plan. Code checks that ids match one to one and that no new dates, years or programs
appear; otherwise the neutral texts from code stay."""

import json
import logging
import re
from collections.abc import Iterable

from app.agent.plan import COST_TRACKING_TITLE
from app.knowledge_base.loader import KnowledgeBase
from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.llm.prompts import load_prompt
from app.llm.schema import LLMOutput
from app.models.contract import FundingPlan, Gap, InstrumentMatch

log = logging.getLogger(__name__)

_MONTHS = "Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember"
_DATE_LIKE = re.compile(
    rf"\b\d{{1,2}}\.\s?\d{{1,2}}\.\s?\d{{2,4}}\b"  # 31.01.2027
    rf"|\b\d{{4}}-\d{{2}}(-\d{{2}})?\b"  # 2027-01-31
    rf"|\b(19|20)\d{{2}}\b"  # 2027
    rf"|\b\d{{1,2}}\.\s?({_MONTHS})"  # 31. Januar
)


class StepText(LLMOutput):
    step_id: str
    title: str
    action: str


class GapHint(LLMOutput):
    gap_id: str
    hint: str


class PlanTexts(LLMOutput):
    steps: list[StepText]
    hints: list[GapHint]


def default_hint(gap: Gap, match: InstrumentMatch) -> str:
    """Neutral hint from the knowledge base texts, used without (or instead of) the LLM."""
    if gap.lever:
        return f"{gap.lever}."
    texts = [c.text for c in match.criteria if c.criterion_id in gap.criterion_ids]
    return f"Noch zu klären: {' '.join(texts)}"


def with_default_hints(matches: list[InstrumentMatch]) -> list[InstrumentMatch]:
    return [
        m.model_copy(
            update={"gaps": [g.model_copy(update={"hint": default_hint(g, m)}) for g in m.gaps]}
        )
        for m in matches
    ]


async def write_plan_texts(
    plan: FundingPlan, matches: list[InstrumentMatch], kb: KnowledgeBase, llm: LLMClient
) -> tuple[FundingPlan, list[InstrumentMatch]]:
    """Plan and matches with LLM texts, or with the neutral defaults if the call or the
    checks fail. A failure here never fails the run."""
    matches = with_default_hints(matches)
    steps = {f"schritt_{i}": e for i, e in enumerate(plan.timeline, start=1)}
    gaps = {_gap_key(m, i): (m, g) for m in matches for i, g in enumerate(m.gaps, start=1)}
    if not steps and not gaps:
        return plan, matches
    payload = {
        "schritte": {
            k: {"phase": e.phase, "titel": e.title, "aktion": e.action, "frist": e.date_rule}
            for k, e in steps.items()
        },
        "luecken": {
            k: {
                "programm": m.program_name,
                "typ": g.type,
                "hebel": g.lever,
                "kriterien": [c.text for c in m.criteria if c.criterion_id in g.criterion_ids],
            }
            for k, (m, g) in gaps.items()
        },
    }
    user = json.dumps(payload, ensure_ascii=False, indent=1)
    try:
        texts = await llm.structured(
            task="plan",
            system=load_prompt("plan"),
            user=user,
            output=PlanTexts,
            tier="main",
            effort="low",
        )
    except LLMError as error:
        log.warning("Fahrplan-Texte: KI-Aufruf fehlgeschlagen (%s), Standardtexte", error.message)
        return plan, matches
    problem = _problem(texts, steps.keys(), gaps.keys(), user, _foreign_programs(kb, matches))
    if problem:
        log.warning("Fahrplan-Texte verworfen: %s. Standardtexte.", problem)
        return plan, matches

    step_texts = {s.step_id: s for s in texts.steps}
    # The cost-tracking step names the claim and cost year; its wording stays as the code wrote it.
    timeline = [
        e
        if e.title == COST_TRACKING_TITLE
        else e.model_copy(update={"title": step_texts[k].title, "action": step_texts[k].action})
        for k, e in steps.items()
    ]
    next_steps = [
        n.model_copy(update={"text": entry.action})
        for n, entry in zip(plan.next_steps, timeline, strict=True)
    ]
    hints = {h.gap_id: h.hint for h in texts.hints}
    matches = [
        m.model_copy(
            update={
                "gaps": [
                    g.model_copy(update={"hint": hints[_gap_key(m, i)]})
                    for i, g in enumerate(m.gaps, start=1)
                ]
            }
        )
        for m in matches
    ]
    return plan.model_copy(update={"timeline": timeline, "next_steps": next_steps}), matches


def _gap_key(match: InstrumentMatch, index: int) -> str:
    return f"luecke_{match.program_id}_{match.instrument_id}_{index}"


def _foreign_programs(kb: KnowledgeBase, matches: list[InstrumentMatch]) -> list[str]:
    mine = {m.program_id for m in matches}
    return [n for p in kb.programs if p.id not in mine for n in (p.name, p.short_name) if n]


def _problem(
    texts: PlanTexts,
    step_ids: Iterable[str],
    gap_ids: Iterable[str],
    source: str,
    foreign: list[str],
) -> str | None:
    if sorted(s.step_id for s in texts.steps) != sorted(step_ids):
        return "Schritte passen nicht zu den IDs"
    if sorted(h.gap_id for h in texts.hints) != sorted(gap_ids):
        return "Hinweise passen nicht zu den IDs"
    known_dates = {m.group(0) for m in _DATE_LIKE.finditer(source)}
    for text in [*(s.title + " " + s.action for s in texts.steps), *(h.hint for h in texts.hints)]:
        new = {m.group(0) for m in _DATE_LIKE.finditer(text)} - known_dates
        if new:
            return f"neue Daten {sorted(new)}"
        if any(name in text for name in foreign):
            return "fremdes Programm genannt"
    return None
