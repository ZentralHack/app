import asyncio
import json

from app.agent.plan_texts import GapHint, PlanTexts, StepText, write_plan_texts
from app.config import REPO_DIR
from app.knowledge_base.loader import KnowledgeBase
from app.llm.errors import LLMOutputError
from app.llm.fake import FakeLLM
from app.models.contract import RunResult

EXAMPLE = RunResult.model_validate(
    json.loads((REPO_DIR / "design" / "examples" / "run_result.json").read_text(encoding="utf-8"))
)
GAPS = ["luecke_lib_lib-beitrag_1", "luecke_lib_lib-beitrag_2"]


def _texts(steps=("schritt_1", "schritt_2"), gaps=GAPS, action="Jetzt erfassen.") -> PlanTexts:
    return PlanTexts(
        steps=[StepText(step_id=s, title="Titel", action=action) for s in steps],
        hints=[GapHint(gap_id=g, hint="Hinweis.") for g in gaps],
    )


def _run(kb, response):
    return asyncio.run(
        write_plan_texts(EXAMPLE.plan, EXAMPLE.matches, kb, FakeLLM({"plan": response}))
    )


def test_texts_are_applied(kb: KnowledgeBase):
    plan, matches = _run(kb, _texts())
    assert [e.action for e in plan.timeline] == ["Jetzt erfassen."] * 2
    assert [e.date_rule for e in plan.timeline] == [e.date_rule for e in EXAMPLE.plan.timeline]
    assert [n.text for n in plan.next_steps] == ["Jetzt erfassen."] * 2
    assert [g.hint for g in matches[0].gaps] == ["Hinweis.", "Hinweis."]


def _assert_defaults(plan, matches):
    assert plan.timeline == EXAMPLE.plan.timeline
    lever_gap, info_gap = matches[0].gaps
    assert lever_gap.hint == "Kompakte Nachhaltigkeitsübersicht (2-3 Seiten) erstellen."
    assert info_gap.hint.startswith("Noch zu klären: Eigene Räumlichkeiten")


def test_wrong_ids_fall_back_to_defaults(kb: KnowledgeBase):
    _assert_defaults(*_run(kb, _texts(steps=("schritt_1",))))
    _assert_defaults(*_run(kb, _texts(gaps=GAPS[:1])))


def test_new_dates_fall_back_to_defaults(kb: KnowledgeBase):
    _assert_defaults(*_run(kb, _texts(action="Bis 30.06.2027 einreichen.")))
    _assert_defaults(*_run(kb, _texts(action="Im Jahr 2028 einreichen.")))


def test_dates_from_the_plan_are_allowed(kb: KnowledgeBase):
    plan, _ = _run(kb, _texts(action="Bis 31. Januar einreichen."))
    assert plan.timeline[1].action == "Bis 31. Januar einreichen."


def test_foreign_program_falls_back(kb: KnowledgeBase):
    _assert_defaults(*_run(kb, _texts(action="Zusätzlich Förderprogramm Energie LU prüfen.")))


def test_llm_failure_falls_back(kb: KnowledgeBase):
    def fail(_):
        raise LLMOutputError("kaputt")

    _assert_defaults(*_run(kb, fail))
