from app.agent.prefilter import prefilter
from app.agent.questions import SKIP_REASON, build_questions, select_questions
from app.knowledge_base.flat import FlatInstrument
from app.knowledge_base.loader import KnowledgeBase
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
    # muss + lever = 5 points each, praesenz_raeume is muss without lever = 3.
    assert [q.id for q in result.questions] == [
        "q_revisionsart",
        "q_nachhaltigkeit",
        "q_auftragsforschung_steuerung",
        "q_kosten_bemessungsjahr",
        "q_raeumlichkeiten",
        "q_kosten_selbst_getragen",
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
    # handelsregister is `annahme` for Sensora: muss without lever = 3, halved = 1.5.
    assert "q_handelsregister" not in [
        q.id for q in build_questions(sensora_profile(), kb).questions
    ]
    # revisionsart as `annahme`: muss with lever = 5, halved = 2.5, still below 3.
    fields = sensora_profile().fields | {"revisionsart": field("ordentlich", "annahme")}
    profile = sensora_profile().model_copy(update={"fields": fields})
    assert "q_revisionsart" not in [q.id for q in build_questions(profile, kb).questions]
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
