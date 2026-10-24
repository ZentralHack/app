import shutil
from pathlib import Path

import pytest

from app.config import KNOWLEDGE_BASE_DIR
from app.knowledge_base.loader import KnowledgeBase, load_knowledge_base

# The tests are pinned to these two reference programs, so they stay stable
# while the knowledge base grows. test_kb_loader.py checks the full knowledge base.
REFERENCE_PROGRAMS = ("lib", "foerderprogramm-energie-lu")


def copy_reference_kb(target: Path) -> Path:
    """Schema, question catalog and the reference programs, copied to `target`."""
    shutil.copytree(KNOWLEDGE_BASE_DIR / "schema", target / "schema")
    shutil.copy(KNOWLEDGE_BASE_DIR / "question_catalog.json", target)
    (target / "programs").mkdir(parents=True)
    for program_id in REFERENCE_PROGRAMS:
        shutil.copy(KNOWLEDGE_BASE_DIR / "programs" / f"{program_id}.json", target / "programs")
    return target


@pytest.fixture(scope="session")
def kb(tmp_path_factory: pytest.TempPathFactory) -> KnowledgeBase:
    return load_knowledge_base(copy_reference_kb(tmp_path_factory.mktemp("kb")))
