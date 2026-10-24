from datetime import date

import pytest

from app.agent.deadlines import deadline, lib_claim_deadline, next_deadline, project_start
from app.knowledge_base.flat import FlatInstrument
from app.knowledge_base.loader import KnowledgeBase
from tests.factories import make_profile

TODAY = date(2026, 10, 24)


def _instrument(kb: KnowledgeBase, key: str) -> FlatInstrument:
    return next(i for i in kb.instruments() if i.key == key)


@pytest.mark.parametrize(
    ("cost_year", "due"),
    [
        (2027, date(2029, 1, 31)),
        (2026, date(2028, 1, 31)),
        (2025, date(2027, 1, 31)),
        # Claim years 2026 and 2027 are both due 31.01.2027.
        (2024, date(2027, 1, 31)),
    ],
)
def test_lib_claim_deadline(cost_year, due):
    assert lib_claim_deadline(cost_year) == due


def test_project_start_formats():
    assert project_start(make_profile(projektstart="2027-03")) == date(2027, 3, 1)
    assert project_start(make_profile(projektstart="2027-03-15")) == date(2027, 3, 15)
    assert project_start(make_profile(projektstart="Fallen erst an")) is None
    assert project_start(make_profile(projektstart=None)) is None


def test_lib_without_project_start_uses_next_fixed_date(kb):
    lib = _instrument(kb, "lib:lib-beitrag")
    assert next_deadline(lib, make_profile(), TODAY) == date(2027, 1, 31)
    assert next_deadline(lib, make_profile(), date(2027, 2, 1)) == date(2028, 1, 31)
    assert next_deadline(lib, make_profile(), date(2028, 2, 1)) is None


def test_lib_with_project_start_uses_cost_year(kb):
    lib = _instrument(kb, "lib:lib-beitrag")
    assert next_deadline(lib, make_profile(projektstart="2027-03"), TODAY) == date(2029, 1, 31)
    # Costs from 2024 on: the first deadline has passed, later years are still open.
    started = make_profile(projektstart="2024-05")
    assert next_deadline(lib, started, date(2027, 3, 1)) == date(2028, 1, 31)


def test_before_project_start(kb):
    pump = _instrument(kb, "foerderprogramm-energie-lu:waermepumpe")
    assert next_deadline(pump, make_profile(projektstart="2026-12"), TODAY) == date(2026, 12, 1)
    assert next_deadline(pump, make_profile(), TODAY) is None


def test_after_completion_has_no_date(kb):
    charging = _instrument(kb, "foerderprogramm-energie-lu:ladeinfrastruktur")
    result = deadline(charging, make_profile(projektstart="2026-12"), TODAY)
    assert result.type == "nach_abschluss"
    assert result.next_date is None
    assert result.rule.startswith("Abschlussunterlagen")
