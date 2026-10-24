from datetime import date

import pytest

from app.agent.timing import apply_timing, before_start_action
from app.config import KNOWLEDGE_BASE_DIR
from app.knowledge_base.loader import KnowledgeBase, load_knowledge_base
from app.models.contract import CriterionResult, SourceLink
from app.models.program import Criterion
from tests.factories import field, make_profile

TODAY = date(2026, 10, 24)


@pytest.fixture(scope="module")
def full_kb() -> KnowledgeBase:
    return load_knowledge_base(KNOWLEDGE_BASE_DIR)


def _criteria(kb: KnowledgeBase) -> dict[str, Criterion]:
    return {
        f"{i.key}:{s.criterion.id}": s.criterion for i in kb.instruments() for s in i.criteria()
    }


def test_every_before_start_criterion_in_the_knowledge_base(full_kb: KnowledgeBase):
    """The rule covers exactly these criteria; a new one shows up here for review."""
    found = {k for k, c in _criteria(full_kb).items() if before_start_action(c)}
    energy = "foerderprogramm-energie-lu"
    assert found == {
        "bfe-pilot-demonstration:pd-finanzhilfe:projektbeginn_nach_vertrag",
        f"{energy}:waermedaemmung:gesuch_vor_baubeginn",
        f"{energy}:waermepumpe:gesuch_vor_installationsbeginn",
        f"{energy}:holzfeuerung:gesuch_vor_installationsbeginn",
        f"{energy}:waermenetz-anschluss:gesuch_vor_installationsbeginn",
        f"{energy}:bonus-ersatz-elektroheizung:gesuch_vor_baubeginn",
        *(
            f"gemeinde-luzern:{i}:gesuch_vor_realisierung"
            for i in (
                "heizungsersatz",
                "desinvestitionsbeitrag",
                "photovoltaik",
                "e-mobilitaet",
                "abwaermenutzung",
            )
        ),
        "klimastiftung-schweiz:innovationsfoerderung:antrag_vor_umsetzung",
        "nrp-luzern:nrp-projektfoerderung:vor_projektstart",
        "prokilowatt:projekte:nicht_begonnen",
    }


def _pump(kb: KnowledgeBase) -> Criterion:
    return _criteria(kb)["foerderprogramm-energie-lu:waermepumpe:gesuch_vor_installationsbeginn"]


def _result(state: str) -> CriterionResult:
    return CriterionResult(
        criterion_id="gesuch_vor_installationsbeginn",
        scope="instrument",
        text="Das Gesuch ist vor Installationsbeginn eingereicht.",
        kind="muss",
        state=state,
        reason="Nicht belegt.",
        evidence=[],
        profile_fields=["projektstart"],
        question=None,
        source=SourceLink(title="Bedingungen", url="https://example.org", locator=None),
    )


def test_future_start_is_fulfillable(full_kb: KnowledgeBase):
    out = apply_timing(
        _pump(full_kb), _result("unbekannt"), make_profile(projektstart="2026-12"), TODAY
    )
    assert out.state == "annahme"
    assert out.reason == "Projekt startet 12/2026. Gesuch vor Installationsbeginn einreichen."
    assert out.evidence == ["projektstart"]


def test_past_start_or_work_begun_stays_open_or_failed(full_kb: KnowledgeBase):
    past = make_profile(projektstart="2026-03")
    assert apply_timing(_pump(full_kb), _result("annahme"), past, TODAY).state == "unbekannt"
    assert (
        apply_timing(_pump(full_kb), _result("nicht_erfuellt"), past, TODAY).state
        == "nicht_erfuellt"
    )
    begun = make_profile(projektstart="2026-12", rueckfrage_gesuch_vor_installationsbeginn="Ja")
    assert (
        apply_timing(_pump(full_kb), _result("nicht_erfuellt"), begun, TODAY).state
        == "nicht_erfuellt"
    )


def test_answer_not_started_without_a_date(full_kb: KnowledgeBase):
    profile = make_profile(rueckfrage_gesuch_vor_installationsbeginn="Nein")
    out = apply_timing(_pump(full_kb), _result("unbekannt"), profile, TODAY)
    assert out.state == "annahme"
    assert out.evidence == ["rueckfrage_gesuch_vor_installationsbeginn"]


def test_no_start_and_other_criteria_are_left_alone(full_kb: KnowledgeBase):
    no_start = make_profile(projektstart=field(None))
    assert apply_timing(_pump(full_kb), _result("unbekannt"), no_start, TODAY).state == "unbekannt"
    lib = _criteria(full_kb)["lib:lib-beitrag:kosten_bemessungsjahr"]
    future = make_profile(projektstart="2027-01")
    assert apply_timing(lib, _result("unbekannt"), future, TODAY).state == "unbekannt"


def test_reached_start_is_open_with_the_problem_even_if_answer_says_not_started(
    full_kb: KnowledgeBase,
):
    past = make_profile(projektstart="2026-10-03")
    out = apply_timing(_pump(full_kb), _result("annahme"), past, TODAY)
    assert out.state == "unbekannt"
    assert out.reason == (
        "Projektstart 10/2026 liegt vor dem Gesuch: "
        "Gesuch muss vor Installationsbeginn eingereicht werden."
    )
    contradiction = make_profile(
        projektstart="2026-10-03", rueckfrage_gesuch_vor_installationsbeginn="Nein"
    )
    assert apply_timing(_pump(full_kb), _result("unbekannt"), contradiction, TODAY).state == (
        "unbekannt"
    )
