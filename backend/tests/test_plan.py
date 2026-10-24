from datetime import date

from app.agent.plan import PlanItem, build_plan
from app.agent.prefilter import prefilter
from app.knowledge_base.flat import FlatInstrument
from app.knowledge_base.loader import KnowledgeBase
from app.models.contract import Gap, InstrumentRef
from app.models.program import CombinationRule
from tests.factories import treuhand_profile


def _instrument(kb: KnowledgeBase, key: str) -> FlatInstrument:
    return next(i for i in kb.instruments() if i.key == key)


def _item(kb, key, fit="passt_gut", gaps=(), deadline=None) -> PlanItem:
    return PlanItem(_instrument(kb, key), fit, list(gaps), deadline)


LIB = "lib:lib-beitrag"
PUMP = "foerderprogramm-energie-lu:waermepumpe"
GRID = "foerderprogramm-energie-lu:waermenetz-anschluss"


def test_sensora_plan(kb: KnowledgeBase):
    plan = build_plan([_item(kb, LIB, deadline=date(2027, 1, 31))], [], kb)
    (entry,) = plan.timeline
    assert entry.phase == "gesuch"
    assert entry.title == "Gesuch Luzerner Innovationsbeitrag"
    assert entry.date == date(2027, 1, 31)
    assert entry.date_rule.startswith("31. Januar des Beitragsjahres")
    assert plan.warnings == []
    assert plan.next_steps[0].link == "https://standortfoerderung.lu.ch/LIB/Gesuch_einreichen"
    assert plan.next_steps[0].due == date(2027, 1, 31)
    assert [c.name for c in plan.contacts] == ["Dienststelle Raum und Wirtschaft (rawi)"]


def test_lever_goes_first_and_not_fitting_is_left_out(kb: KnowledgeBase):
    gap = Gap(
        type="anpassung",
        criterion_ids=["partner_forschungspartner"],
        lever="Forschungspartner beiziehen",
        hint=None,
        source=None,
    )
    plan = build_plan(
        [
            _item(kb, LIB, "passt_mit_anpassung", [gap], date(2027, 1, 31)),
            _item(kb, PUMP, "passt_nicht"),
        ],
        [],
        kb,
    )
    assert [(e.phase, e.action) for e in plan.timeline] == [
        ("jetzt", "Forschungspartner beiziehen"),
        ("gesuch", "Gesuch einreichen."),
    ]


def test_phases_and_order(kb: KnowledgeBase):
    plan = build_plan(
        [
            _item(kb, LIB, deadline=date(2027, 1, 31)),
            _item(kb, PUMP, deadline=date(2026, 12, 1)),
        ],
        [],
        kb,
    )
    assert [(e.phase, e.instrument_id) for e in plan.timeline] == [
        ("vor_projektstart", "waermepumpe"),
        ("gesuch", "lib-beitrag"),
    ]
    assert plan.timeline[0].date_rule == "vor Installationsbeginn"


def test_lib_deducts_other_funding(kb: KnowledgeBase):
    plan = build_plan([_item(kb, LIB), _item(kb, PUMP)], [], kb)
    (warning,) = plan.warnings
    assert warning.type == "abzug"
    assert warning.items == [
        InstrumentRef(program_id="lib", instrument_id="lib-beitrag"),
        InstrumentRef(program_id="foerderprogramm-energie-lu", instrument_id="waermepumpe"),
    ]
    assert warning.source.locator == "N 142"


def test_rule_on_one_instrument(kb: KnowledgeBase):
    assert build_plan([_item(kb, GRID)], [], kb).warnings == []
    (warning,) = build_plan([_item(kb, PUMP), _item(kb, GRID)], [], kb).warnings
    assert warning.type == "bedingt"
    assert {i.instrument_id for i in warning.items} == {"waermepumpe", "waermenetz-anschluss"}


def test_nothing_fits_names_contacts(kb: KnowledgeBase):
    rejected = prefilter(treuhand_profile(), kb.instruments()).rejected
    plan = build_plan([], rejected, kb)
    assert plan.timeline == []
    assert plan.next_steps == []
    assert {c.name for c in plan.contacts} >= {"Dienststelle Raum und Wirtschaft (rawi)"}
    assert len(plan.contacts) >= 2


def _with_rule(item: PlanItem, rule_type: str, target: str) -> PlanItem:
    rule = CombinationRule.model_validate({"with": target, "type": rule_type, "text": "Regel"})
    program = item.item.program.model_copy(update={"combination_rules": [rule]})
    return PlanItem(FlatInstrument(program, item.item.instrument), item.fit, [], item.next_deadline)


def test_prerequisite_comes_first(kb: KnowledgeBase):
    lib = _with_rule(_item(kb, LIB, deadline=date(2027, 1, 31)), "voraussetzung", PUMP)
    pump = _item(kb, PUMP, deadline=date(2027, 6, 1))
    plan = build_plan([lib, pump], [], kb)
    assert [e.instrument_id for e in plan.timeline] == ["waermepumpe", "lib-beitrag"]


def test_recommended_step_goes_to_now(kb: KnowledgeBase):
    # The instrument with the rule is the earlier step (like ITZ before Innosuisse).
    lib = _with_rule(_item(kb, LIB), "empfohlen_vorher", PUMP)
    plan = build_plan([lib, _item(kb, PUMP)], [], kb)
    assert plan.timeline[0].phase == "jetzt"
    assert plan.timeline[0].instrument_id == "lib-beitrag"
    assert plan.timeline[0].action == "Regel"
    # Without the later instrument, there is nothing to prepare for.
    assert build_plan([lib], [], kb).timeline[0].phase == "gesuch"


def test_dead_target_is_ignored(kb: KnowledgeBase):
    lib = _with_rule(_item(kb, LIB), "ausgeschlossen", "innosuisse")
    assert build_plan([lib, _item(kb, PUMP)], [], kb).warnings == []
