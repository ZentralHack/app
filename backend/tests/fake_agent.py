"""A FakeLLM that answers like a careful model, from the request content alone."""

import json

from app.agent.matching import CriterionCheck, MatchingOutput
from app.agent.plan_texts import PlanTexts
from app.llm.errors import LLMOutputError
from app.llm.fake import FakeLLM


def careful_matching(user: str) -> MatchingOutput:
    """`erfuellt` with a real quote where a criterion's profile field is known,
    `unbekannt` otherwise."""
    data = json.loads(user)
    profile = data["profil"]
    checks = []
    for criterion in data["instrument"]["kriterien"]:
        fields = [f for f in criterion["profilfelder"] if f in profile]
        if fields:
            value = profile[fields[0]]["wert"]
            quote = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            check = CriterionCheck(
                criterion_id=criterion["criterion_id"],
                state="erfuellt",
                reason="Laut Profil erfüllt.",
                evidence_fields=fields,
                quotes=[quote],
            )
        else:
            check = CriterionCheck(
                criterion_id=criterion["criterion_id"],
                state="unbekannt",
                reason="Dazu fehlen Angaben.",
                evidence_fields=[],
                quotes=[],
            )
        checks.append(check)
    return MatchingOutput(criteria=checks, exclusion_hits=[], lever_ids=[])


def failing_once(answer):
    """Fails the first call, then answers like `answer`."""
    calls = {"n": 0}

    def respond(user: str):
        calls["n"] += 1
        if calls["n"] == 1:
            raise LLMOutputError("Die KI hat keine gültige Antwort geliefert.")
        return answer(user)

    return respond


def plan_failure(_: str) -> PlanTexts:
    raise LLMOutputError("kaputt")


def fake_llm(**overrides) -> FakeLLM:
    return FakeLLM({"matching": careful_matching, "plan": plan_failure, **overrides})
