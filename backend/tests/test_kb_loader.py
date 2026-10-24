import json
import shutil
from pathlib import Path

import pytest

from app.config import KNOWLEDGE_BASE_DIR
from app.knowledge_base.enums import PROFILE_ENUMS
from app.knowledge_base.loader import KnowledgeBase, find_dead_references, load_knowledge_base
from app.models.contract import InstrumentRef
from tests.conftest import REFERENCE_PROGRAMS, copy_reference_kb


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    """A copy of the reference knowledge base that tests may break."""
    return copy_reference_kb(tmp_path)


def test_full_knowledge_base_is_valid():
    """Every program file in knowledge_base/programs loads, and every reference resolves."""
    kb = load_knowledge_base(KNOWLEDGE_BASE_DIR)
    assert [(f.program_id, f.errors) for f in kb.invalid] == []
    assert set(REFERENCE_PROGRAMS) <= {p.id for p in kb.programs}
    assert find_dead_references(kb) == []


def test_loads_all_programs(kb: KnowledgeBase):
    assert {p.id for p in kb.programs} == {"lib", "foerderprogramm-energie-lu"}
    assert kb.invalid == []


def test_instruments_are_flat_and_carry_program_data(kb: KnowledgeBase):
    flat = {i.key: i for i in kb.instruments()}
    assert len(flat) == 7
    lib = flat["lib:lib-beitrag"]
    scopes = [(c.scope, c.criterion.id) for c in lib.criteria()]
    assert scopes[0] == ("programm", "unternehmerisch_taetig")
    assert ("instrument", "fei_taetigkeit") in scopes
    assert lib.program.scope.cantons == ["LU"]
    assert [lever.text for lever in lib.levers_for("revision")] == [
        "Prüfbericht nach SA-CH (PS-CH 700) für das Bemessungsjahr erstellen lassen, "
        "falls keine ordentliche Revision besteht"
    ]


def test_find_and_source_link(kb: KnowledgeBase):
    lib = kb.find(InstrumentRef(program_id="lib", instrument_id="lib-beitrag"))
    assert lib is not None
    link = lib.source_link(lib.program.general_criteria[1].source)
    assert link is not None
    assert link.locator == "N 20"
    assert link.title.startswith("Handbuch")
    assert kb.find(InstrumentRef(program_id="lib", instrument_id="gibt-es-nicht")) is None


def test_invalid_file_is_skipped_and_reported(kb_dir: Path):
    broken = json.loads((kb_dir / "programs" / "lib.json").read_text(encoding="utf-8"))
    broken["id"] = "kaputt"
    broken["level"] = "planet"
    (kb_dir / "programs" / "kaputt.json").write_text(json.dumps(broken), encoding="utf-8")
    (kb_dir / "programs" / "kein-json.json").write_text("{", encoding="utf-8")

    kb = load_knowledge_base(kb_dir)

    assert {p.id for p in kb.programs} == {"lib", "foerderprogramm-energie-lu"}
    invalid = {f.program_id: f for f in kb.invalid}
    assert set(invalid) == {"kaputt", "kein-json"}
    assert any(e.startswith("level:") for e in invalid["kaputt"].errors)
    assert invalid["kein-json"].errors[0].startswith("Kein gültiges JSON")


def test_id_must_match_file_name(kb_dir: Path):
    shutil.copy(kb_dir / "programs" / "lib.json", kb_dir / "programs" / "lib-kopie.json")
    kb = load_knowledge_base(kb_dir)
    assert [f.program_id for f in kb.invalid] == ["lib"]
    assert "Dateinamen" in kb.invalid[0].errors[0]


def test_dead_references_are_found(kb: KnowledgeBase):
    dead = find_dead_references(kb)
    # Reserved id, referenced by lib.json, no file planned (CLAUDE.md).
    assert dead == ["lib: combination_rules[].with 'steuerliche-innovationsfoerderung-lu'"]


def test_dead_lever_reference(kb_dir: Path):
    path = kb_dir / "programs" / "lib.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["instruments"][0]["levers"][0]["affects_criteria"] = ["gibt_es_nicht"]
    path.write_text(json.dumps(data), encoding="utf-8")
    dead = find_dead_references(load_knowledge_base(kb_dir))
    assert "lib:lib-beitrag: levers[].affects_criteria 'gibt_es_nicht'" in dead


def test_resolves_combination_targets(kb: KnowledgeBase):
    assert kb.resolves("*")
    assert kb.resolves("lib")
    assert kb.resolves("foerderprogramm-energie-lu:waermenetz-anschluss")
    assert not kb.resolves("foerderprogramm-energie-lu:gibt-es-nicht")
    assert not kb.resolves("innosuisse")


def test_question_index_from_criteria(kb: KnowledgeBase):
    revision = kb.questions["revision"]
    assert revision.profile_field == "rueckfrage_revision"
    assert revision.options[-1] == "Weiss nicht"
    assert revision.options.count("Weiss nicht") == 1
    # Same criterion id in several energy instruments → one question.
    assert "gesuch_vor_installationsbeginn" in kb.questions
    # "Weiss nicht" is added where the knowledge base leaves it out.
    assert kb.questions["kosten_bemessungsjahr"].options[-1] == "Weiss nicht"


def test_profile_enums_cover_filter_fields():
    assert set(PROFILE_ENUMS) == {"applicant_type", "art_des_vorhabens", "branche", "partner"}
    assert "forschungspartner" in PROFILE_ENUMS["partner"]
