from datetime import date

from app.agent.prefilter import RULES, prefilter
from app.knowledge_base.enums import PROFILE_ENUMS
from app.knowledge_base.flat import FlatInstrument
from app.knowledge_base.loader import KnowledgeBase
from app.knowledge_base.partners import partner_lever
from app.models.contract import Rejected
from tests.factories import (
    aarau_profile,
    field,
    make_profile,
    sensora_profile,
    treuhand_profile,
    vague_profile,
)


def _lib(kb: KnowledgeBase, **filter_update) -> FlatInstrument:
    """The LIB instrument, optionally with a changed filter or availability."""
    lib = next(i for i in kb.instruments() if i.program.id == "lib")
    availability = filter_update.pop("availability", lib.instrument.availability)
    instrument = lib.instrument.model_copy(
        update={
            "filter": lib.instrument.filter.model_copy(update=filter_update),
            "availability": availability,
        }
    )
    return FlatInstrument(lib.program, instrument)


def _rules(rejected: list[Rejected]) -> dict[str, str]:
    return {r.instrument_id: r.rule for r in rejected}


def test_rule_order_matches_contract():
    assert [rule for rule, _ in RULES] == [
        "verfuegbarkeit",
        "kanton",
        "gesuchsteller",
        "vorhaben",
        "branche",
        "mitarbeitende",
        "unternehmensalter",
    ]


def test_sensora_keeps_lib_and_drops_energy_by_project_type(kb: KnowledgeBase):
    result = prefilter(sensora_profile(), kb.instruments())
    assert [i.key for i in result.kept] == ["lib:lib-beitrag"]
    assert len(result.rejected) == 6
    assert set(_rules(result.rejected).values()) == {"vorhaben"}
    assert all(r.availability_status is None for r in result.rejected)


def test_outside_lucerne_drops_cantonal_programs(kb: KnowledgeBase):
    result = prefilter(aarau_profile(), kb.instruments())
    assert result.kept == []
    assert set(_rules(result.rejected).values()) == {"kanton"}
    lib = next(r for r in result.rejected if r.program_id == "lib")
    assert lib.reason == "Gilt nur im Kanton LU; Ihr Standort liegt im Kanton AG."


def test_nothing_fits_the_company_event(kb: KnowledgeBase):
    result = prefilter(treuhand_profile(), kb.instruments())
    assert result.kept == []
    assert set(_rules(result.rejected).values()) == {"vorhaben"}


def test_missing_values_keep_everything(kb: KnowledgeBase):
    result = prefilter(vague_profile(), kb.instruments())
    assert len(result.kept) == 7
    assert result.rejected == []


def test_availability_rejects_with_status_and_next_round(kb: KnowledgeBase):
    closed = _lib(
        kb,
        availability=_lib(kb).instrument.availability.model_copy(
            update={"status": "runde_geschlossen", "next_round": date(2027, 3, 1)}
        ),
    )
    (rejected,) = prefilter(vague_profile(), [closed]).rejected
    assert rejected.rule == "verfuegbarkeit"
    assert rejected.availability_status == "runde_geschlossen"
    assert rejected.next_round == date(2027, 3, 1)
    assert rejected.reason.endswith("Nächste Runde ab 01.03.2027.")


def test_first_rule_wins(kb: KnowledgeBase):
    profile = make_profile(standort_kanton="ZH", art_des_vorhabens=["export"])
    (rejected,) = prefilter(profile, [_lib(kb)]).rejected
    assert rejected.rule == "kanton"


def test_applicant_type(kb: KnowledgeBase):
    profile = make_profile(applicant_type=["privatperson"])
    assert _rules(prefilter(profile, [_lib(kb)]).rejected) == {"lib-beitrag": "gesuchsteller"}
    profile = make_profile(applicant_type=["privatperson", "kmu"])
    assert prefilter(profile, [_lib(kb)]).rejected == []


def test_sector_only_when_restricted(kb: KnowledgeBase):
    profile = make_profile(branche=["handel"])
    assert prefilter(profile, [_lib(kb)]).rejected == []
    restricted = _lib(kb, sectors=["tourismus", "hotellerie"])
    assert _rules(prefilter(profile, [restricted]).rejected) == {"lib-beitrag": "branche"}


def test_employees_and_company_age(kb: KnowledgeBase):
    limited = _lib(kb, employees_max=10, company_age_years_max=5)
    (rejected,) = prefilter(make_profile(mitarbeitende=18), [limited]).rejected
    assert rejected.rule == "mitarbeitende"
    assert rejected.reason == "Gilt für Unternehmen mit höchstens 10 Mitarbeitenden; Sie haben 18."
    (rejected,) = prefilter(make_profile(unternehmensalter=7), [limited]).rejected
    assert rejected.rule == "unternehmensalter"
    assert prefilter(make_profile(mitarbeitende=10, unternehmensalter=5), [limited]).kept


def test_assumed_values_count_as_known(kb: KnowledgeBase):
    profile = make_profile(standort_kanton=field("BE", "annahme"))
    assert _rules(prefilter(profile, [_lib(kb)]).rejected) == {"lib-beitrag": "kanton"}


def test_missing_partner_is_a_criterion_not_a_reject(kb: KnowledgeBase):
    needs_partner = _lib(kb, required_partners=["forschungspartner"])
    result = prefilter(make_profile(partner=[]), [needs_partner])
    assert result.rejected == []
    (partner,) = [c for c in result.kept[0].criteria() if c.scope == "filter"]
    assert partner.criterion.id == "partner_forschungspartner"
    assert partner.criterion.kind == "muss"
    assert partner.criterion.profile_fields == ["partner"]
    assert partner_lever(partner.criterion.id) == "Forschungspartner beiziehen"


def test_every_partner_type_has_a_lever():
    for partner in PROFILE_ENUMS["partner"]:
        assert partner_lever(f"partner_{partner}")
