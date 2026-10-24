import asyncio
import json

import pytest

from app.agent.matching import (
    CriterionCheck,
    ExclusionHit,
    MatchingOutput,
    check_instrument,
    matching_input,
    post_check,
)
from app.knowledge_base.flat import FlatInstrument
from app.knowledge_base.loader import KnowledgeBase
from app.llm.fake import FakeLLM
from tests.contract_check import assert_contract
from tests.factories import sensora_profile


@pytest.fixture
def lib(kb: KnowledgeBase) -> FlatInstrument:
    return next(i for i in kb.instruments() if i.program.id == "lib")


def _check(criterion_id, state, fields=(), quotes=(), reason="Begründung."):
    return CriterionCheck(
        criterion_id=criterion_id,
        state=state,
        reason=reason,
        evidence_fields=list(fields),
        quotes=list(quotes),
    )


def _output(*checks, hits=(), levers=()):
    return MatchingOutput(criteria=list(checks), exclusion_hits=list(hits), lever_ids=list(levers))


def _states(result) -> dict[str, str]:
    return {c.criterion_id: c.state for c in result.criteria}


def test_input_has_criteria_ids_exclusions_and_levers(lib):
    data = json.loads(matching_input(lib, sensora_profile()))
    ids = [c["criterion_id"] for c in data["instrument"]["kriterien"]]
    assert ids[0] == "unternehmerisch_taetig"
    assert "fei_taetigkeit" in ids
    assert "ausschluss_1" in data["instrument"]["ausschluesse"]
    assert data["instrument"]["hebel"]["hebel_1"].startswith("Kompakte Nachhaltigkeit")
    assert "revisionsart" in data["fehlende_felder"]
    assert "revisionsart" not in data["profil"]


def test_evidence_rule(lib):
    result = post_check(
        lib,
        sensora_profile(),
        _output(
            _check("fei_taetigkeit", "erfuellt", ["art_des_vorhabens"], ["Prototyp bauen"]),
            _check("neuartig", "erfuellt", ["vorhaben_beschreibung"], ["ein Zauberstab"]),
            _check("systematisch", "erfuellt", [], ["Budget rund CHF 400'000"]),
            _check("revision", "nicht_erfuellt", ["revisionsart"], ["keine Revision"]),
            _check("hr_luzern", "erfuellt", ["handelsregister"], ["Emmen"]),
            _check("kosten_selbst_getragen", "nicht_anwendbar"),
            _check("auftragsforschung_steuerung", "nicht_anwendbar"),
        ),
    )
    states = _states(result)
    assert states["fei_taetigkeit"] == "erfuellt"
    assert states["neuartig"] == "unbekannt"  # quote not in the profile
    assert states["systematisch"] == "unbekannt"  # no profile field
    assert states["revision"] == "unbekannt"  # revisionsart is missing
    assert states["hr_luzern"] == "annahme"  # only an assumed field
    assert states["kosten_selbst_getragen"] == "unbekannt"  # no applies_if
    assert states["auftragsforschung_steuerung"] == "nicht_anwendbar"
    assert result.downgrades == 5


def test_missing_unknown_and_duplicate_criteria(lib):
    result = post_check(
        lib,
        sensora_profile(),
        _output(
            _check("erfunden", "erfuellt", ["budget"], ["400'000"]),
            _check("fei_taetigkeit", "erfuellt", ["art_des_vorhabens"], ["Prototyp bauen"]),
            _check("fei_taetigkeit", "nicht_erfuellt", ["art_des_vorhabens"], ["Prototyp"]),
        ),
    )
    assert len(result.criteria) == len(lib.criteria())
    assert "erfunden" not in _states(result)
    assert _states(result)["fei_taetigkeit"] == "erfuellt"
    assert _states(result)["revision"] == "unbekannt"


def test_sources_come_from_the_knowledge_base(lib):
    result = post_check(lib, sensora_profile(), _output())
    revision = next(c for c in result.criteria if c.criterion_id == "revision")
    assert revision.source.locator == "N 14-15"
    assert revision.scope == "programm"
    for criterion in result.criteria:
        assert_contract("CriterionResult", criterion)


def test_exclusion_hits_need_existing_id_and_quote(lib):
    hit = ExclusionHit(exclusion_id="ausschluss_2", quotes=["bei Pilotkunden testen"])
    unproven = ExclusionHit(exclusion_id="ausschluss_3", quotes=["erfunden"])
    unknown = ExclusionHit(exclusion_id="ausschluss_99", quotes=["Prototyp"])
    result = post_check(lib, sensora_profile(), _output(hits=[hit, unproven, unknown]))
    assert result.exclusion_hits == [
        "Marketing, Markteinführung, Verkauf und Unternehmenskommunikation"
    ]


def test_lever_ids_must_exist(lib):
    result = post_check(lib, sensora_profile(), _output(levers=["hebel_2", "hebel_9", "hebel_2"]))
    assert len(result.lever_texts) == 1
    assert result.lever_texts[0].startswith("Prüfbericht nach SA-CH")


def test_check_instrument_calls_main_model(lib):
    llm = FakeLLM({"matching": _output()})
    asyncio.run(check_instrument(lib, sensora_profile(), llm))
    assert (llm.calls[0].tier, llm.calls[0].effort) == ("main", "low")
    assert "Ohne Beleg kein `erfuellt`" in llm.calls[0].system
