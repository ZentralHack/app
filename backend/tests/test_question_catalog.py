"""Stage 1 of the catalog validation, run on the real catalog and on broken copies."""

import json
import shutil
from pathlib import Path

import pytest

from app.config import KNOWLEDGE_BASE_DIR
from app.knowledge_base.catalog import CatalogEntry
from app.knowledge_base.catalog_checks import STALE, check_catalog
from app.knowledge_base.loader import KnowledgeBase, load_knowledge_base

CATALOG = KNOWLEDGE_BASE_DIR / "question_catalog.json"


def _raw() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def _errors(kb: KnowledgeBase, field: str, change) -> list[str]:
    raw = _raw()
    change(raw[field])
    entries = {field: CatalogEntry.model_validate(raw[field])}
    findings = check_catalog(entries, kb.programs, list(kb.instruments()))
    return [f.message for f in findings if f.severity == "fehler"]


def test_real_catalog_has_no_errors_and_is_current(kb: KnowledgeBase):
    assert kb.catalog.error is None
    errors = [f for f in kb.catalog.findings if f.severity == "fehler"]
    assert errors == []
    assert STALE not in [f.message for f in kb.catalog.findings]
    assert set(kb.catalog.entries) == {
        "partner",
        "revisionsart",
        "projektstart",
        "handelsregister",
        "raeumlichkeiten",
        "baujahr",
    }


def test_all_entries_wait_for_review(kb: KnowledgeBase):
    assert {e.review.status for e in kb.catalog.entries.values()} == {"needs_review"}


def test_partner_decides_the_generated_partner_criterion(kb: KnowledgeBase):
    decision = kb.catalog.entries["partner"].deciding()[0]
    assert decision.criterion == "filter:partner_forschungspartner"
    assert decision.states == {"erfuellt", "nicht_erfuellt"}


@pytest.mark.parametrize(
    ("field", "change", "message"),
    [
        ("revisionsart", lambda e: e["options"][0].update(value="gut"), "passt nicht zum Typ"),
        ("raeumlichkeiten", lambda e: e["options"][0].update(value="ja"), "passt nicht zum Typ"),
        ("partner", lambda e: e["options"][0].update(value=["hochschule"]), "passt nicht zum Typ"),
        ("revisionsart", lambda e: e["options"].pop(), "Weiss nicht"),
        ("revisionsart", lambda e: e.update(text="Wie prüfst du deine Rechnung?"), "Du-Form"),
        ("revisionsart", lambda e: e.update(text="Gilt das für den LIB?"), "Programmname"),
        ("revisionsart", lambda e: e.update(text="Wo ist der standort_kanton?"), "Feldname"),
        ("revisionsart", lambda e: e.update(text="Wer prüft"), "'?'"),
        ("revisionsart", lambda e: e.update(text="Grösse?".replace("ss", "ß")), "'ß'"),
        ("baujahr", lambda e: e.update(unit=None), "unit, min und max"),
        (
            "revisionsart",
            lambda e: e["decides"][0].update(criterion="lib:gibt_es_nicht"),
            "kein Kriterium",
        ),
        (
            "revisionsart",
            lambda e: e["decides"][0].update(map=[{"value": "ordentlich", "state": "erfuellt"}]),
            "nur einen Status",
        ),
        ("revisionsart", lambda e: e.update(decides=[]), "fehlt in decides und not_decidable"),
        (
            "partner",
            lambda e: e["decides"][0].update(criterion="filter:partner_freunde"),
            "kein Kriterium",
        ),
        (
            "baujahr",
            lambda e: e["decides"][0]["map"][0].update(max="2000"),
            "min/max-Grenzen",
        ),
    ],
)
def test_code_checks_find_errors(kb: KnowledgeBase, field, change, message):
    errors = _errors(kb, field, change)
    assert any(message in e for e in errors), errors


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    shutil.copytree(KNOWLEDGE_BASE_DIR / "schema", tmp_path / "schema")
    shutil.copytree(KNOWLEDGE_BASE_DIR / "programs", tmp_path / "programs")
    shutil.copy(CATALOG, tmp_path / CATALOG.name)
    return tmp_path


def test_changed_criterion_makes_entry_stale_but_keeps_it(kb_dir: Path):
    path = kb_dir / "programs" / "lib.json"
    lib = json.loads(path.read_text(encoding="utf-8"))
    lib["general_criteria"][4]["text"] += " Neu formuliert."  # revision
    path.write_text(json.dumps(lib), encoding="utf-8")
    kb = load_knowledge_base(kb_dir)
    assert "revisionsart" in kb.catalog.entries
    assert [f.field for f in kb.catalog.findings if f.message == STALE] == ["revisionsart"]
    assert kb.catalog.review_counts()["veraltet"] == 1


def test_broken_entry_is_dropped(kb_dir: Path):
    raw = _raw()
    raw["revisionsart"]["options"].pop()
    (kb_dir / CATALOG.name).write_text(json.dumps(raw), encoding="utf-8")
    kb = load_knowledge_base(kb_dir)
    assert "revisionsart" not in kb.catalog.entries
    assert "partner" in kb.catalog.entries


@pytest.mark.parametrize("content", [None, "{", '{"partner": {"text": "?"}}'])
def test_missing_or_invalid_catalog_does_not_stop_loading(kb_dir: Path, content):
    path = kb_dir / CATALOG.name
    if content is None:
        path.unlink()
    else:
        path.write_text(content, encoding="utf-8")
    kb = load_knowledge_base(kb_dir)
    assert kb.catalog.entries == {}
    assert kb.catalog.error.startswith("Fragenkatalog")
    assert len(kb.programs) == 2
    assert "revision" in kb.criterion_questions
