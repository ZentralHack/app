import pytest

from app.agent.prefilter import prefilter
from app.agent.questions import SKIP_REASON, build_questions, criterion_question, select_questions
from app.config import KNOWLEDGE_BASE_DIR
from app.knowledge_base.flat import FlatInstrument
from app.knowledge_base.loader import KnowledgeBase, load_knowledge_base
from app.models.contract import CriterionRef
from tests.contract_check import assert_contract
from tests.factories import field, make_profile, sensora_profile


def _questions(kb: KnowledgeBase, profile, **kwargs):
    candidates = prefilter(profile, kb.instruments()).kept
    return select_questions(
        profile, candidates, kb.catalog.entries, kb.criterion_questions, **kwargs
    )


def test_sensora_questions_by_points(kb: KnowledgeBase):
    result = build_questions(sensora_profile(), kb)
    assert_contract("QuestionSet", result)
    # LIB is Luzern money (times 2 times 1.5): muss + lever = 15, muss alone = 9; the assumed
    # handelsregister counts half (4.5) and comes after the questions on missing fields.
    assert [q.id for q in result.questions] == [
        "q_revisionsart",
        "q_nachhaltigkeit",
        "q_auftragsforschung_steuerung",
        "q_kosten_bemessungsjahr",
        "q_raeumlichkeiten",
        "q_kosten_selbst_getragen",
        "q_handelsregister",
        "q_keine_ausstaende",
    ]
    revision = result.questions[0]
    assert revision.profile_field == "revisionsart"
    assert revision.text == "Wie wird die Jahresrechnung Ihres Unternehmens geprüft?"
    assert revision.options[-1] == "Weiss nicht"
    assert revision.why.endswith("Entscheidet über: Luzerner Innovationsbeitrag.")
    assert revision.affects == [
        CriterionRef(program_id="lib", instrument_id=None, criterion_id="revision")
    ]
    # Criteria the catalog cannot decide keep their own question.
    fallback = result.questions[3]
    assert fallback.profile_field == "rueckfrage_kosten_bemessungsjahr"
    assert fallback.affects[0].instrument_id == "lib-beitrag"


def test_assumed_field_counts_half_and_is_prefilled(kb: KnowledgeBase):
    # handelsregister is `annahme` for Sensora: 3 x 2 x 1.5 = 9, halved = 4.5, after every
    # LIB question on a missing field.
    ids = [q.id for q in build_questions(sensora_profile(), kb).questions]
    assert ids.index("q_handelsregister") > ids.index("q_raeumlichkeiten")
    # revisionsart as `annahme`: 15 halved = 7.5, behind the missing fields with 9 or more.
    fields = sensora_profile().fields | {"revisionsart": field("ordentlich", "annahme")}
    profile = sensora_profile().model_copy(update={"fields": fields})
    ids = [q.id for q in build_questions(profile, kb).questions]
    assert ids.index("q_revisionsart") > ids.index("q_kosten_selbst_getragen")
    # Over the threshold with several instruments: prefill is the assumed answer's label.
    profile = make_profile(art_des_vorhabens=["heizungsersatz"], baujahr=field(1985, "annahme"))
    baujahr = next(q for q in build_questions(profile, kb).questions if q.id == "q_baujahr")
    assert baujahr.prefill == "1985"


def test_cap(kb: KnowledgeBase):
    assert len(_questions(kb, sensora_profile(), max_questions=3).questions) == 3


def test_answered_field_is_not_asked_again(kb: KnowledgeBase):
    fields = sensora_profile().fields | {"revisionsart": field("ordentlich")}
    profile = sensora_profile().model_copy(update={"fields": fields})
    assert "q_revisionsart" not in [q.id for q in build_questions(profile, kb).questions]


def test_number_question_from_catalog(kb: KnowledgeBase):
    result = build_questions(make_profile(art_des_vorhabens=["gebaeudesanierung"]), kb)
    assert_contract("QuestionSet", result)
    baujahr = next(q for q in result.questions if q.id == "q_baujahr")
    assert baujahr.input == "zahl"
    assert baujahr.unit == "Jahr"
    assert baujahr.options == ["Weiss nicht"]


def test_points_add_up_across_instruments(kb: KnowledgeBase):
    result = build_questions(make_profile(art_des_vorhabens=["heizungsersatz"]), kb)
    question = next(q for q in result.questions if q.id == "q_gebaeude_luzern")
    # Program-wide muss criterion on 4 heating instruments: 12 points, one ref only.
    assert len(question.affects) == 1
    assert question.why.count(",") == 3


def test_partner_question_decides_generated_partner_criterion(kb: KnowledgeBase):
    lib = next(i for i in kb.instruments() if i.program.id == "lib")
    # Without LIB's own criteria, so its other open questions do not push q_partner out.
    needs_partner = lib.instrument.model_copy(
        update={
            "criteria": [],
            "filter": lib.instrument.filter.model_copy(
                update={"required_partners": ["forschungspartner"]}
            ),
        }
    )
    item = FlatInstrument(lib.program.model_copy(update={"general_criteria": []}), needs_partner)
    result = select_questions(
        make_profile(partner=None), [item], kb.catalog.entries, kb.criterion_questions
    )
    partner = next(q for q in result.questions if q.id == "q_partner")
    assert (
        CriterionRef(
            program_id="lib", instrument_id="lib-beitrag", criterion_id="partner_forschungspartner"
        )
        in partner.affects
    )


def test_skip_when_nothing_would_change(kb: KnowledgeBase):
    result = select_questions(sensora_profile(), [], kb.catalog.entries, kb.criterion_questions)
    assert result.questions == []
    assert result.skip_reason == SKIP_REASON
    assert_contract("QuestionSet", result)


def test_soll_alone_is_below_threshold(kb: KnowledgeBase):
    lib = next(i for i in kb.instruments() if i.program.id == "lib")
    criterion = lib.instrument.criteria[1].model_copy(update={"kind": "soll"})  # neuartig
    instrument = lib.instrument.model_copy(update={"criteria": [criterion], "levers": []})
    program = lib.program.model_copy(update={"general_criteria": []})
    profile = make_profile(vorhaben_beschreibung=None)
    result = select_questions(
        profile, [FlatInstrument(program, instrument)], {}, kb.criterion_questions
    )
    assert result.questions == []


def _scoped(kb: KnowledgeBase, program: str, instrument: str, criterion: str):
    item = next(
        i for i in kb.instruments() if i.program.id == program and i.instrument.id == instrument
    )
    return item, next(s for s in item.criteria() if s.criterion.id == criterion)


def test_criterion_question_prefers_the_deciding_catalog_question(kb: KnowledgeBase):
    item, scoped = _scoped(kb, "lib", "lib-beitrag", "hr_luzern")
    question = criterion_question(item, scoped, kb)
    assert question is not None
    assert (question.id, question.profile_field) == ("q_handelsregister", "handelsregister")
    assert question.prefill is None
    assert question.affects == [
        CriterionRef(program_id="lib", instrument_id=None, criterion_id="hr_luzern")
    ]
    assert_contract("Question", question)


@pytest.fixture(scope="module")
def full_kb() -> KnowledgeBase:
    return load_knowledge_base(KNOWLEDGE_BASE_DIR)


def test_criterion_question_falls_back_to_the_criterion_question(full_kb: KnowledgeBase):
    item, scoped = _scoped(full_kb, "pronovo", "kleiv", "zustimmung_grundeigentuemer")
    question = criterion_question(item, scoped, full_kb)
    assert question is not None
    assert question.id == "q_zustimmung_grundeigentuemer"
    assert question.profile_field == "rueckfrage_zustimmung_grundeigentuemer"
    assert question.options[-1] == "Weiss nicht"


def test_no_question_when_nothing_in_a_profile_decides_it(full_kb: KnowledgeBase):
    item, scoped = _scoped(full_kb, "eic-accelerator", "eic-accelerator", "auswahl_jury")
    assert criterion_question(item, scoped, full_kb) is None


def test_a_given_field_is_never_asked_again(full_kb: KnowledgeBase):
    """Projektstart is given: the timing criterion gets its own question, not Projektstart."""
    item, scoped = _scoped(
        full_kb, "foerderprogramm-energie-lu", "waermepumpe", "gesuch_vor_installationsbeginn"
    )
    empty = criterion_question(item, scoped, full_kb, make_profile())
    assert empty is not None and empty.profile_field == "projektstart"
    given = criterion_question(item, scoped, full_kb, make_profile(projektstart="2026-12"))
    assert given is not None
    assert given.profile_field == "rueckfrage_gesuch_vor_installationsbeginn"


def test_sensora_asks_what_decides_lib_first(full_kb: KnowledgeBase):
    """Luzern money first: the LIB questions come before anything only EIC or advice needs."""
    questions = build_questions(sensora_profile(), full_kb).questions
    ids = [q.id for q in questions]
    flat = {i.key: i for i in full_kb.instruments()}

    def only_competition_or_advice(q) -> bool:
        items = [
            flat[f"{a.program_id}:{a.instrument_id}"]
            if a.instrument_id
            else next(i for i in flat.values() if i.program.id == a.program_id)
            for a in q.affects
        ]
        return all(
            i.program.id == "eic-accelerator" or i.instrument.instrument_type == "beratung"
            for i in items
        )

    lib = ["q_revisionsart", "q_handelsregister", "q_raeumlichkeiten"]
    assert set(lib) <= set(ids)
    later = [i for i, q in enumerate(questions) if only_competition_or_advice(q)]
    assert max(ids.index(q) for q in lib) < min(later, default=len(ids))
