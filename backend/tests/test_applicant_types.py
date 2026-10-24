from app.agent.applicant_types import IMPLIES, with_implied
from app.knowledge_base.enums import PROFILE_ENUMS


def test_every_entry_uses_knowledge_base_types():
    allowed = PROFILE_ENUMS["applicant_type"]
    for narrow, broad in IMPLIES.items():
        assert narrow in allowed
        assert broad <= allowed


def test_start_up_is_a_company_and_small_companies_are_kmu():
    assert with_implied(["startup"], None) == {"startup", "unternehmen"}
    assert with_implied(["startup"], 3) == {"startup", "unternehmen", "kmu"}
    assert with_implied(["unternehmen"], 249) == {"unternehmen", "kmu"}
    assert with_implied(["unternehmen"], 250) == {"unternehmen", "grossunternehmen"}


def test_nothing_is_invented_for_others():
    assert with_implied(["gemeinde"], 35) == {"gemeinde"}
    assert with_implied(["privatperson"], 4) == {"privatperson"}
    assert with_implied(["grossunternehmen"], 100) == {"grossunternehmen", "unternehmen"}


def test_founder_or_successor_applies_as_the_company():
    takeover = with_implied(["privatperson"], 4, ["nachfolge", "finanzierung"])
    assert {"unternehmen", "kmu"} <= takeover
    assert "startup" in with_implied(["privatperson"], None, ["gruendung"])
    assert with_implied(["privatperson"], 4, ["investition"]) == {"privatperson"}
