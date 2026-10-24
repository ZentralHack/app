from app.agent.prefilter import prefilter
from app.agent.questions import SKIP_REASON, build_questions
from app.knowledge_base.flat import FlatInstrument
from app.knowledge_base.loader import KnowledgeBase
from app.models.contract import CriterionRef
from tests.factories import field, make_profile, sensora_profile


def _candidates(kb: KnowledgeBase, profile) -> list[FlatInstrument]:
    return prefilter(profile, kb.instruments()).kept


def test_sensora_questions_by_points(kb: KnowledgeBase):
    profile = sensora_profile()
    result = build_questions(profile, _candidates(kb, profile), kb.questions)
    # muss + lever = 5 points each, praesenz_raeume is muss without lever = 3.
    assert [q.id for q in result.questions] == [
        "q_revision",
        "q_nachhaltigkeit",
        "q_kosten_bemessungsjahr",
        "q_praesenz_raeume",
    ]
    assert result.skip_reason is None
    revision = result.questions[0]
    assert revision.profile_field == "rueckfrage_revision"
    assert revision.options[-1] == "Weiss nicht"
    assert revision.input == "auswahl"
    assert revision.why == "Entscheidet über: Luzerner Innovationsbeitrag."
    assert revision.affects == [
        CriterionRef(program_id="lib", instrument_id=None, criterion_id="revision")
    ]
    instrument_level = result.questions[2].affects[0]
    assert instrument_level.instrument_id == "lib-beitrag"


def test_assumed_fields_are_not_asked(kb: KnowledgeBase):
    # hr_luzern only uses standort_kanton and handelsregister, both `annahme` for Sensora.
    profile = sensora_profile()
    ids = [q.id for q in build_questions(profile, _candidates(kb, profile), kb.questions).questions]
    assert "q_hr_luzern" not in ids


def test_cap(kb: KnowledgeBase):
    profile = sensora_profile()
    result = build_questions(profile, _candidates(kb, profile), kb.questions, max_questions=3)
    assert len(result.questions) == 3


def test_answered_question_is_not_asked_again(kb: KnowledgeBase):
    fields = sensora_profile().fields | {"rueckfrage_revision": field("Ordentliche Revision")}
    profile = sensora_profile().model_copy(update={"fields": fields})
    ids = [q.id for q in build_questions(profile, _candidates(kb, profile), kb.questions).questions]
    assert "q_revision" not in ids


def test_points_add_up_across_instruments(kb: KnowledgeBase):
    profile = make_profile(art_des_vorhabens=["heizungsersatz"])
    result = build_questions(profile, _candidates(kb, profile), kb.questions)
    first = result.questions[0]
    # Program-wide muss criterion on 4 heating instruments → asked first, one ref only.
    assert first.id == "q_gebaeude_luzern"
    assert len(first.affects) == 1
    assert first.why.count(",") == 3


def test_skip_when_nothing_would_change(kb: KnowledgeBase):
    result = build_questions(sensora_profile(), [], kb.questions)
    assert result.questions == []
    assert result.skip_reason == SKIP_REASON


def test_soll_alone_is_below_threshold(kb: KnowledgeBase):
    lib = next(i for i in kb.instruments() if i.program.id == "lib")
    criterion = lib.instrument.criteria[1].model_copy(update={"kind": "soll"})  # neuartig
    instrument = lib.instrument.model_copy(update={"criteria": [criterion], "levers": []})
    program = lib.program.model_copy(update={"general_criteria": []})
    profile = make_profile(vorhaben_beschreibung=None)
    result = build_questions(profile, [FlatInstrument(program, instrument)], kb.questions)
    assert result.questions == []
