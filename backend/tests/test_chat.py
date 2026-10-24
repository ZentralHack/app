"""Follow-up chat: post-check, out of scope, citations, general terms, suggestions, API."""

import asyncio
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.agent.chat import (
    FALLBACK,
    ChatOutput,
    ChatTarget,
    ChatTargetNotFoundError,
    Citation,
    answer,
    find_target,
    post_check,
    suggestions,
)
from app.config import DEMO_DIR, KNOWLEDGE_BASE_DIR, Settings
from app.knowledge_base.loader import KnowledgeBase, load_knowledge_base
from app.llm.fake import FakeLLM
from app.main import create_app
from app.models.contract import ChatMessage, InstrumentRef, RunResult
from tests.contract_check import assert_contract

LIB = InstrumentRef(program_id="lib", instrument_id="lib-beitrag")
INNOSUISSE = InstrumentRef(
    program_id="innosuisse", instrument_id="innovationsprojekt-umsetzungspartner"
)


@pytest.fixture
def result() -> RunResult:
    data = json.loads((DEMO_DIR / "sensor-prototyp.json").read_text(encoding="utf-8"))
    return RunResult.model_validate(data)


@pytest.fixture(scope="module")
def full_kb() -> KnowledgeBase:
    """Innosuisse is not among the reference programs; the demo run needs it."""
    return load_knowledge_base(KNOWLEDGE_BASE_DIR)


@pytest.fixture
def lib(result: RunResult, kb: KnowledgeBase) -> ChatTarget:
    return find_target(result, LIB, kb)


def _output(text, basis="belegt", citations=(), out_of_scope=False) -> ChatOutput:
    return ChatOutput(
        out_of_scope=out_of_scope,
        answer=text,
        basis=basis,
        citations=[Citation(source_id=s, locator=loc) for s, loc in citations],
    )


def _check(target: ChatTarget, output: ChatOutput):
    llm = FakeLLM({"chat": output})
    response = asyncio.run(answer(target, [ChatMessage(role="user", text="Frage?")], llm))
    assert_contract("ChatResponse", response.model_dump(mode="json"))
    return response, llm


def test_cited_answer_keeps_known_citation(lib):
    response, llm = _check(
        lib,
        _output(
            "Laut Handbuch zählen Forschung und experimentelle Entwicklung.",
            citations=[("handbuch", "N 51-72")],
        ),
    )
    assert response.basis == "belegt"
    assert [(c.title, c.locator) for c in response.citations] == [
        ("Handbuch Luzerner Innovationsbeitrag (LIB)", "N 51-72")
    ]
    assert response.contact is None
    call = llm.calls[0]
    assert (call.task, call.tier, call.effort) == ("chat", "main", "low")
    assert '"programmdatei"' in call.user and "N 51-72" in call.user


def test_unknown_citation_is_dropped_and_basis_not_belegt(lib):
    response, _ = _check(
        lib,
        _output(
            "Forschung zählt.",
            citations=[("handbuch", "N 51-72"), ("handbuch", "N 999"), ("erfunden", None)],
        ),
    )
    assert response.basis == "nicht_belegt"
    assert [c.locator for c in response.citations] == ["N 51-72"]
    assert response.contact is not None and response.contact.email == "innovationsbeitrag@lu.ch"


def test_belegt_without_citation_becomes_abgeleitet(lib):
    response, _ = _check(lib, _output("Das Kriterium ist laut Ergebnis offen."))
    assert response.basis == "abgeleitet"


def test_out_of_scope_gives_fallback_with_contact(lib):
    response, _ = _check(lib, _output("Gern schreibe ich Ihr Gesuch.", out_of_scope=True))
    assert response.answer == FALLBACK
    assert response.basis == "nicht_belegt"
    assert response.citations == []
    assert response.contact.name.startswith("Dienststelle Raum und Wirtschaft")


@pytest.mark.parametrize(
    "text",
    [
        "Sie erhalten 30 % der Personalkosten.",
        "Sie haben Anspruch auf den Beitrag.",
        "Sie sind berechtigt, ein Gesuch einzureichen.",
        "Der Beitrag wird Ihnen garantiert.",
    ],
)
def test_binding_wording_gives_fallback(lib, text):
    response, _ = _check(lib, _output(text, citations=[("handbuch", "N 51-72")]))
    assert (response.answer, response.basis) == (FALLBACK, "nicht_belegt")


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        ("Die Frist ist der 31. Januar 2027.", True),
        ("Personalkosten zählen mit 30 %, höchstens 50 %.", True),
        ("Die Frist ist der 28. Februar 2027.", False),
        ("Der Beitrag liegt bei CHF 120'000.", False),
        ("Personalkosten zählen mit 35 %.", False),
    ],
)
def test_numbers_must_come_from_context(lib, text, ok):
    response, _ = _check(lib, _output(text, basis="abgeleitet"))
    assert (response.answer == text) is ok
    assert (response.basis == "abgeleitet") is ok


def test_general_term_without_figures_is_allowed(lib):
    text = "Overhead sind Gemeinkosten, die nicht direkt einem Projekt zugeordnet werden."
    response, _ = _check(lib, _output(text, basis="allgemein", citations=[("handbuch", None)]))
    assert (response.answer, response.basis, response.citations) == (text, "allgemein", [])
    assert response.contact is None


@pytest.mark.parametrize(
    "text",
    [
        "Eigenmittel sind meist mindestens 20 % des Projekts.",
        "Ein Bemessungsjahr endet oft am 31.12.",
        "Die Revision kostet oft CHF 5000.",
        "Bemessungsjahr ist beim Luzerner Innovationsbeitrag das Geschäftsjahr zwei Jahre vorher.",
    ],
)
def test_general_term_with_figures_or_program_gives_fallback(lib, text):
    response, _ = _check(lib, _output(text, basis="allgemein"))
    assert (response.answer, response.basis) == (FALLBACK, "nicht_belegt")


def test_model_nicht_belegt_gives_fallback(lib):
    response = post_check(lib, _output("Weiss ich nicht.", basis="nicht_belegt"), "{}")
    assert (response.answer, response.basis) == (FALLBACK, "nicht_belegt")


def test_context_contains_only_this_instrument(result, full_kb):
    target = find_target(result, INNOSUISSE, full_kb)
    llm = FakeLLM({"chat": _output("Ja.", basis="abgeleitet")})
    asyncio.run(answer(target, [ChatMessage(role="user", text="Kombination?")], llm))
    context = json.loads(llm.calls[0].user)["kontext"]
    assert context["angebot"]["instrument_id"] == INNOSUISSE.instrument_id
    assert [w["andere_angebote"] for w in context["kombinationswarnungen"]] == [
        ["Innovationsmentoring"]
    ]
    assert all(e["instrument_id"] == INNOSUISSE.instrument_id for e in context["fahrplan"])
    assert context["programmdatei"]["id"] == "innosuisse"


def test_history_is_passed_and_last_message_is_the_question(lib):
    llm = FakeLLM({"chat": _output("Ja.", basis="abgeleitet")})
    messages = [
        ChatMessage(role="user", text="Erste Frage"),
        ChatMessage(role="assistant", text="Erste Antwort"),
        ChatMessage(role="user", text="Zweite Frage"),
    ]
    asyncio.run(answer(lib, messages, llm))
    user = json.loads(llm.calls[0].user)
    assert user["frage"] == "Zweite Frage"
    assert [m["text"] for m in user["verlauf"]] == ["Erste Frage", "Erste Antwort"]


def test_unknown_or_unfinished_target(result, kb):
    with pytest.raises(ChatTargetNotFoundError):
        find_target(result, InstrumentRef(program_id="lib", instrument_id="gibt-es-nicht"), kb)


def test_suggestions_lib(lib):
    questions = suggestions(lib).questions
    assert_contract("ChatSuggestions", suggestions(lib).model_dump(mode="json"))
    assert len(questions) <= 3
    assert questions[-1].topic == "frist"
    assert questions[-1].text == "Was muss bis zum 31.01.2027 eingereicht sein?"


def test_suggestions_with_adjustment_and_combination(result, full_kb):
    target = find_target(result, INNOSUISSE, full_kb)
    questions = suggestions(target).questions
    topics = [q.topic for q in questions]
    assert topics[0] == "passung"
    assert len(questions) == 3
    assert "kombination" in topics
    combination = next(q for q in questions if q.topic == "kombination")
    assert "Innovationsmentoring" in combination.text


def test_api_chat_logs_anonymised_question(result, kb, tmp_path):
    log = tmp_path / "chat.jsonl"
    settings = Settings(_env_file=None, demo_today=date(2026, 10, 24), chat_log=log)
    llm = FakeLLM(
        {"chat": _output("Laut Handbuch zählt Forschung.", citations=[("handbuch", "N 51-72")])}
    )
    with TestClient(create_app(settings, kb, llm), raise_server_exceptions=False) as client:
        recorder = client.app.state.runs.create(result.profile, date(2026, 10, 24))
        recorder.update(result.model_copy(update={"run_id": recorder.run_id}))
        recorder.set_busy(False)
        base = f"/api/runs/{recorder.run_id}/chat/lib/lib-beitrag"

        suggested = client.get(f"{base}/suggestions")
        assert suggested.status_code == 200
        assert_contract("ChatSuggestions", suggested.json())

        body = {"messages": [{"role": "user", "text": "Was zählt als Forschung?"}]}
        response = client.post(base, json=body)
        assert response.status_code == 200, response.text
        assert_contract("ChatResponse", response.json())
        assert response.json()["basis"] == "belegt"

        assert (
            client.post(f"/api/runs/{recorder.run_id}/chat/lib/nope", json=body).json()["code"]
            == "angebot_nicht_gefunden"
        )
        last_assistant = {"messages": [{"role": "assistant", "text": "Hallo"}]}
        assert client.post(base, json=last_assistant).status_code == 400
        assert client.post(base, json={"messages": []}).status_code == 400

    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 1
    assert set(entries[0]) == {"ts", "program_id", "instrument_id", "question", "basis"}
    assert entries[0]["question"] == "Was zählt als Forschung?"
    assert entries[0]["basis"] == "belegt"
