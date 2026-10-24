from app.agent.project_types import IMPLIES, with_implied
from app.knowledge_base.enums import PROFILE_ENUMS


def test_every_entry_uses_knowledge_base_types():
    allowed = PROFILE_ENUMS["art_des_vorhabens"]
    for narrow, broad in IMPLIES.items():
        assert narrow in allowed
        assert broad <= allowed
        assert narrow not in broad


def test_implied_types_are_added():
    assert with_implied(["prototyp"]) == {"prototyp", "entwicklung"}
    study = with_implied(["klinische_studie", "export"])
    assert study == {"klinische_studie", "forschung", "export"}


def test_nothing_is_removed_or_invented():
    assert with_implied([]) == set()
    assert with_implied(["entwicklung"]) == {"entwicklung"}
