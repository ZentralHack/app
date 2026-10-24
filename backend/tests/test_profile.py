import asyncio
import json

import pytest

from app.agent.answers import apply_answers
from app.agent.errors import InvalidInputError
from app.agent.profile import ExtractedField, ExtractedFields, ProfileExtraction, extract_profile
from app.config import REPO_DIR
from app.knowledge_base.loader import KnowledgeBase
from app.knowledge_base.profile_fields import FIELD_TYPES, field_descriptions
from app.llm.fake import FakeLLM
from app.models.contract import Answer, ProfileRequest
from tests.contract_check import assert_contract
from tests.factories import sensora_profile

SENSORA = json.loads((REPO_DIR / "tests" / "projects" / "sensor-prototyp.json").read_text())
VAGUE = json.loads((REPO_DIR / "tests" / "projects" / "zu-vage.json").read_text())


def _extraction(summary: str = "Ein Satz.", **fields: tuple) -> ProfileExtraction:
    """Keyword values are (value, status, quote); every other field is `fehlt`."""
    missing = ExtractedField(value=None, status="fehlt", quote=None, note=None)
    values = dict.fromkeys(FIELD_TYPES, missing)
    for name, (value, status, quote) in fields.items():
        values[name] = ExtractedField(value=value, status=status, quote=quote, note=None)
    return ProfileExtraction(summary=summary, fields=ExtractedFields(**values))


def _run(req: dict, extraction: ProfileExtraction):
    llm = FakeLLM({"profile": extraction})
    return asyncio.run(extract_profile(ProfileRequest.model_validate(req), llm)), llm


def test_core_fields_match_contract():
    assert set(FIELD_TYPES) == set(field_descriptions())


def test_sensora_profile():
    extraction = _extraction(
        standort_kanton=("LU", "annahme", "aus Emmen"),
        art_des_vorhabens=(["entwicklung", "prototyp"], "angegeben", "einen Prototyp bauen"),
        vorhaben_beschreibung=("Optischer Sensor", "angegeben", "neuartigen optischen Sensor"),
        laufzeit=(18.0, "angegeben", "in den nächsten 18 Monaten"),
        partner=([], "angegeben", "Einen Forschungspartner haben wir noch nicht"),
    )
    response, llm = _run(SENSORA["input"], extraction)
    assert_contract("ProfileResponse", response)
    fields = response.profile.fields
    assert response.status == "ok"
    assert set(fields) == set(FIELD_TYPES)
    assert fields["standort_kanton"].status == "annahme"
    assert fields["standort_kanton"].origin == "text"
    assert fields["laufzeit"].value == 18
    # Form fields win and count as stated.
    assert fields["mitarbeitende"].origin == "formular"
    assert fields["budget"].value == 400000
    assert isinstance(fields["budget"].value, int)
    assert fields["revisionsart"].status == "fehlt"
    assert llm.calls[0].tier == "small"
    assert llm.calls[0].effort == "low"
    assert "`partner`" in llm.calls[0].system
    assert "forschungspartner" in llm.calls[0].system
    assert SENSORA["input"]["text"] in llm.calls[0].user


def test_quote_not_in_text_downgrades_to_assumption():
    extraction = _extraction(
        art_des_vorhabens=(["prototyp"], "angegeben", "wir bauen einen Prototyp aus Titan"),
        vorhaben_beschreibung=("Sensor", "angegeben", "neuartigen   optischen\nSensor"),
    )
    fields = _run(SENSORA["input"], extraction)[0].profile.fields
    assert fields["art_des_vorhabens"].status == "annahme"
    assert fields["art_des_vorhabens"].quote is None
    assert fields["art_des_vorhabens"].origin is None
    # Whitespace differences do not count as a different quote.
    assert fields["vorhaben_beschreibung"].status == "angegeben"


def test_wrong_types_and_unknown_enums_are_dropped():
    extraction = _extraction(
        mitarbeitende=("viele", "annahme", None),
        revisionsart=("streng", "annahme", None),
        art_des_vorhabens=(["prototyp", "raketen"], "annahme", None),
    )
    fields = _run({"text": SENSORA["input"]["text"]}, extraction)[0].profile.fields
    assert fields["mitarbeitende"].status == "fehlt"
    assert fields["revisionsart"].status == "fehlt"
    assert fields["art_des_vorhabens"].value == ["prototyp"]


def test_too_vague_asks_what_the_money_is_for():
    response, _ = _run(VAGUE["input"], _extraction())
    assert_contract("ProfileResponse", response)
    assert response.status == "needs_clarification"
    assert response.profile is None
    assert response.clarification.question == "Wofür brauchen Sie die Förderung?"


def _answer(field: str, answer: str, question_id: str | None = None) -> Answer:
    return Answer(question_id=question_id or f"q_{field}", profile_field=field, answer=answer)


def test_apply_catalog_answers(kb: KnowledgeBase):
    profile = apply_answers(
        sensora_profile(),
        [
            _answer("revisionsart", "Ordentliche Revision"),
            _answer("raeumlichkeiten", "Nein, nur eine Domiziladresse (c/o)"),
            _answer("partner", "Wir suchen noch einen Partner"),
            _answer("baujahr", "1'985"),
            _answer("projektstart", "2027-03"),
        ],
        kb,
    )
    fields = profile.fields
    assert fields["revisionsart"].value == "ordentlich"
    assert fields["revisionsart"].origin == "rueckfrage"
    assert fields["revisionsart"].status == "angegeben"
    assert "Ordentliche Revision" in fields["revisionsart"].note
    assert fields["raeumlichkeiten"].value is False
    assert fields["partner"].value == []
    assert fields["baujahr"].value == 1985
    assert fields["projektstart"].value == "2027-03"
    assert_contract("ProjectProfile", profile)


def test_dont_know_leaves_the_field(kb: KnowledgeBase):
    profile = apply_answers(sensora_profile(), [_answer("revisionsart", "Weiss nicht")], kb)
    assert profile.fields["revisionsart"].status == "fehlt"


def test_apply_criterion_answer(kb: KnowledgeBase):
    answer = _answer("rueckfrage_nachhaltigkeit", "Ja", "q_nachhaltigkeit")
    field = apply_answers(sensora_profile(), [answer], kb).fields["rueckfrage_nachhaltigkeit"]
    assert field.value == "Ja"
    assert field.origin == "rueckfrage"


@pytest.mark.parametrize(
    "answer",
    [
        _answer("revisionsart", "Sehr gut"),
        _answer("baujahr", "1700"),
        _answer("baujahr", "neunzehnhundert"),
        _answer("baujahr", "1985.5"),
        _answer("projektstart", "März"),
        _answer("revisionsart", "Ordentliche Revision", "q_falsch"),
        _answer("rueckfrage_nachhaltigkeit", "Vielleicht", "q_nachhaltigkeit"),
        _answer("gibt_es_nicht", "Ja"),
    ],
)
def test_invalid_answers_are_rejected(kb: KnowledgeBase, answer):
    with pytest.raises(InvalidInputError):
        apply_answers(sensora_profile(), [answer], kb)


def test_duplicate_answers_are_rejected(kb: KnowledgeBase):
    answers = [_answer("revisionsart", "Ordentliche Revision")] * 2
    with pytest.raises(InvalidInputError):
        apply_answers(sensora_profile(), answers, kb)
