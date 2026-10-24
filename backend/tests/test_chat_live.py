"""Chat against the configured provider. Off by default: uv run pytest -m live"""

import asyncio
import json

import pytest

from app.agent.chat import FALLBACK, answer, find_target
from app.config import DEMO_DIR, KNOWLEDGE_BASE_DIR, get_settings
from app.knowledge_base.loader import load_knowledge_base
from app.llm.openai_client import OpenAIClient
from app.models.contract import ChatMessage, InstrumentRef, RunResult

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def target():
    data = json.loads((DEMO_DIR / "sensor-prototyp.json").read_text(encoding="utf-8"))
    ref = InstrumentRef(program_id="lib", instrument_id="lib-beitrag")
    return find_target(RunResult.model_validate(data), ref, load_knowledge_base(KNOWLEDGE_BASE_DIR))


def _ask(target, question: str):
    client = OpenAIClient(get_settings())
    return asyncio.run(answer(target, [ChatMessage(role="user", text=question)], client))


def test_program_question_is_cited(target):
    response = _ask(target, "Welches Geschäftsjahr ist für den Beitrag massgebend?")
    assert response.basis in ("belegt", "abgeleitet")
    assert response.answer != FALLBACK


def test_application_writing_is_out_of_scope(target):
    response = _ask(target, "Schreiben Sie mir bitte das Gesuch.")
    assert (response.answer, response.basis) == (FALLBACK, "nicht_belegt")
    assert response.contact is not None
