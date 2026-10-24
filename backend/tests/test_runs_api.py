"""The whole chain through the HTTP API with a fake LLM. Every response and every SSE
event is validated against design/contract.schema.json."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.agent.profile import ExtractedField, ExtractedFields, ProfileExtraction
from app.config import REPO_DIR, Settings
from app.knowledge_base.loader import KnowledgeBase
from app.knowledge_base.profile_fields import FIELD_TYPES
from app.main import create_app
from tests.contract_check import assert_contract
from tests.factories import aarau_profile, sensora_profile, treuhand_profile
from tests.fake_agent import careful_matching, failing_once, fake_llm

SETTINGS = Settings(_env_file=None, demo_today="2026-10-24")


def _client(kb: KnowledgeBase, llm) -> TestClient:
    return TestClient(create_app(SETTINGS, kb, llm), raise_server_exceptions=False)


def _post(client, path, body, status=200):
    response = client.post(path, json=body)
    assert response.status_code == status, response.text
    return response.json() if response.content else None


def _wait(client, run_id) -> dict:
    for _ in range(200):
        result = client.get(f"/api/runs/{run_id}").json()
        assert_contract("RunResult", result)
        if result["status"] != "laeuft" and all(m["status"] != "laeuft" for m in result["matches"]):
            return result
        time.sleep(0.01)
    raise AssertionError("Lauf wird nicht fertig")


def _events(client, run_id, last: int = 0) -> list[dict]:
    headers = {"Last-Event-ID": str(last)} if last else {}
    with client.stream("GET", f"/api/runs/{run_id}/events", headers=headers) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        text = "".join(response.iter_text())
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        event = json.loads(lines["data"])
        assert int(lines["id"]) == event["seq"]
        assert lines["event"] == event["type"]
        assert_contract("TraceEvent", event)
        events.append(event)
    return events


def _run(client, profile, answers=()) -> tuple[dict, list[dict]]:
    body = {"profile": profile.model_dump(mode="json"), "answers": list(answers)}
    run_id = _post(client, "/api/runs", body, 202)["run_id"]
    result = _wait(client, run_id)
    return result, _events(client, run_id)


def test_sensora_full_chain(kb: KnowledgeBase):
    with _client(kb, fake_llm()) as client:
        questions = _post(
            client, "/api/questions", {"profile": sensora_profile().model_dump(mode="json")}
        )
        assert_contract("QuestionSet", questions)
        answers = [
            {
                "question_id": "q_revisionsart",
                "profile_field": "revisionsart",
                "answer": "Ordentliche Revision",
            },
            {
                "question_id": "q_nachhaltigkeit",
                "profile_field": "rueckfrage_nachhaltigkeit",
                "answer": "Weiss nicht",
            },
        ]
        result, events = _run(client, sensora_profile(), answers)

    assert result["status"] == "fertig"
    (lib,) = result["matches"]
    assert lib["status"] == "fertig"
    assert lib["fit"] in {"passt_gut", "passt_mit_anpassung"}
    assert lib["rank"] == 1
    revision = next(c for c in lib["criteria"] if c["criterion_id"] == "revision")
    assert revision["state"] == "erfuellt"
    assert revision["source"]["locator"] == "N 14-15"
    assert {g["type"] for g in lib["gaps"]} == {"infos_fehlen"}
    assert all(g["hint"] for g in lib["gaps"])  # standard texts after the failed plan call
    assert len(result["rejected"]) == 6
    assert result["plan"]["timeline"][0]["date"] == "2027-01-31"
    assert result["disclaimer"] == "Orientierungshilfe, keine verbindliche Beurteilung"
    assert [e["type"] for e in events] == [
        "run_started",
        "step_started",
        "prefilter_result",
        "step_completed",
        "step_started",
        "instrument_started",
        "instrument_completed",
        "step_completed",
        "step_started",
        "step_completed",
        "step_started",
        "plan_ready",
        "step_completed",
        "run_completed",
    ]
    assert events[-1]["data"]["fits"]["passt_nicht"] == 6


def test_replay_after_last_event_id(kb: KnowledgeBase):
    with _client(kb, fake_llm()) as client:
        body = {"profile": sensora_profile().model_dump(mode="json"), "answers": []}
        run_id = _post(client, "/api/runs", body, 202)["run_id"]
        _wait(client, run_id)
        events = _events(client, run_id, last=10)
    assert [e["seq"] for e in events] == [11, 12, 13, 14]


def test_outside_lucerne(kb: KnowledgeBase):
    with _client(kb, fake_llm()) as client:
        result, events = _run(client, aarau_profile())
    assert result["status"] == "fertig"
    assert result["matches"] == []
    assert {r["rule"] for r in result["rejected"]} == {"kanton"}
    assert result["plan"]["contacts"]
    assert events[-1]["type"] == "run_completed"


def test_nothing_fits(kb: KnowledgeBase):
    with _client(kb, fake_llm()) as client:
        result, _ = _run(client, treuhand_profile())
    assert result["matches"] == []
    assert {r["rule"] for r in result["rejected"]} == {"vorhaben"}
    names = {c["name"] for c in result["plan"]["contacts"]}
    assert "Dienststelle Raum und Wirtschaft (rawi)" in names


def test_failed_check_is_healed_by_retry(kb: KnowledgeBase):
    with _client(kb, fake_llm(matching=failing_once(careful_matching))) as client:
        result, events = _run(client, sensora_profile())
        (lib,) = result["matches"]
        assert lib["status"] == "fehler"
        assert lib["fit"] is None
        assert lib["error"]
        assert result["status"] == "fertig"  # one failed instrument never fails the run
        failed = next(e for e in events if e["type"] == "instrument_failed")
        assert failed["data"]["retryable"] is True

        ref = {"program_id": "lib", "instrument_id": "lib-beitrag"}
        _post(client, f"/api/runs/{result['run_id']}/retry", ref, 202)
        healed = _wait(client, result["run_id"])
        assert healed["matches"][0]["status"] == "fertig"
        assert healed["matches"][0]["fit"] is not None
        after = _events(client, result["run_id"], last=len(events))
        assert [e["type"] for e in after] == [
            "instrument_started",
            "instrument_completed",
            "plan_ready",
        ]

        # Nothing left to retry.
        error = _post(client, f"/api/runs/{result['run_id']}/retry", ref, 409)
        assert_contract("ApiError", error)
        assert error["code"] == "pruefung_laeuft"


def _extraction(**fields) -> ProfileExtraction:
    missing = ExtractedField(value=None, status="fehlt", quote=None, note=None)
    values = dict.fromkeys(FIELD_TYPES, missing) | fields
    return ProfileExtraction(summary="Ein Satz.", fields=ExtractedFields(**values))


def test_profile_endpoint_and_too_vague(kb: KnowledgeBase):
    vague = json.loads((REPO_DIR / "tests/projects/zu-vage.json").read_text())["input"]
    with _client(kb, fake_llm(profile=_extraction())) as client:
        response = _post(client, "/api/profile", vague)
    assert_contract("ProfileResponse", response)
    assert response["status"] == "needs_clarification"


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/profile", {"text": ""}),
        ("/api/profile", {"text": "Sensor", "mitarbeitende": "18"}),
        ("/api/profile", {"text": "Sensor", "extra": 1}),
        ("/api/runs", {"profile": {"input_text": "x", "summary": "x", "fields": {}}}),
    ],
)
def test_invalid_requests_give_400(kb: KnowledgeBase, path, body):
    with _client(kb, fake_llm()) as client:
        error = _post(client, path, body, 400)
    assert_contract("ApiError", error)
    assert error["code"] == "ungueltige_eingabe"


def test_unknown_enum_in_client_profile_gives_400(kb: KnowledgeBase):
    profile = sensora_profile().model_dump(mode="json")
    profile["fields"]["branche"]["value"] = ["raumfahrt"]
    with _client(kb, fake_llm()) as client:
        error = _post(client, "/api/questions", {"profile": profile}, 400)
        assert "branche" in error["message"]
        error = _post(client, "/api/runs", {"profile": profile, "answers": []}, 400)
    assert error["code"] == "ungueltige_eingabe"


def test_invalid_answer_gives_400(kb: KnowledgeBase):
    answer = {"question_id": "q_revisionsart", "profile_field": "revisionsart", "answer": "Gut"}
    body = {"profile": sensora_profile().model_dump(mode="json"), "answers": [answer]}
    with _client(kb, fake_llm()) as client:
        assert _post(client, "/api/runs", body, 400)["code"] == "ungueltige_eingabe"


def test_unknown_run_and_route(kb: KnowledgeBase):
    with _client(kb, fake_llm()) as client:
        for path in ("/api/runs/run_x", "/api/runs/run_x/events"):
            response = client.get(path)
            assert response.status_code == 404
            assert response.json()["code"] == "run_nicht_gefunden"
        response = client.get("/api/gibt-es-nicht")
        assert response.status_code == 404
        assert_contract("ApiError", response.json())


def test_without_llm_runs_give_503(kb: KnowledgeBase):
    with TestClient(create_app(SETTINGS, kb)) as client:
        body = {"profile": sensora_profile().model_dump(mode="json"), "answers": []}
        error = _post(client, "/api/runs", body, 503)
        assert error["code"] == "ki_nicht_verfuegbar"
        # Questions are pure code and work without the LLM.
        _post(client, "/api/questions", {"profile": body["profile"]})
