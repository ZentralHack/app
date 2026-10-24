import pytest

from app.config import KNOWLEDGE_BASE_DIR
from app.knowledge_base.loader import KnowledgeBase, load_knowledge_base


@pytest.fixture(scope="session")
def kb() -> KnowledgeBase:
    return load_knowledge_base(KNOWLEDGE_BASE_DIR)
