"""DEMO_REPLAY plays a stored result back through the normal API, without any LLM."""

import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import REPO_DIR, Settings
from app.demo import load_demo_cases, profile_before_answers
from app.knowledge_base.loader import KnowledgeBase
from app.main import create_app
from app.models.contract import ProjectProfile
from tests.contract_check import assert_contract
from tests.test_runs_api import _events, _post, _wait

EXAMPLE = REPO_DIR / "design" / "examples" / "run_result.json"


def test_replay_without_llm(kb: KnowledgeBase, tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.demo.CHECK_DELAY_S", (0.0, 0.0))
    monkeypatch.setattr("app.demo.PLAN_DELAY_S", 0.0)
    monkeypatch.setattr("app.demo.STEP_DELAY_S", 0.0)
    shutil.copy(EXAMPLE, tmp_path / "sensora.json")
    (tmp_path / "kaputt.json").write_text("{}", encoding="utf-8")
    demo = load_demo_cases(tmp_path)
    stored = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    settings = Settings(_env_file=None, demo_replay=True)

    with TestClient(create_app(settings, kb, demo=demo)) as client:
        text = stored["profile"]["input_text"]
        profile = _post(client, "/api/profile", {"text": text})
        assert_contract("ProfileResponse", profile)
        before = profile_before_answers(ProjectProfile.model_validate(stored["profile"]))
        assert profile["profile"] == before.model_dump(mode="json")

        body = {"profile": profile["profile"], "answers": []}
        run_id = _post(client, "/api/runs", body, 202)["run_id"]
        result = _wait(client, run_id)
        events = _events(client, run_id)

        assert result["profile"] == profile["profile"], "the run reports the profile it was sent"

        form = {"text": text, "gemeinde": "Musterwil", "mitarbeitende": 35, "budget_chf": 2800000}
        with_form = _post(client, "/api/profile", form)["profile"]["fields"]
        for name, value in [
            ("standort_gemeinde", "Musterwil"),
            ("mitarbeitende", 35),
            ("budget", 2800000),
        ]:
            assert with_form[name] == {
                "value": value,
                "status": "angegeben",
                "origin": "formular",
                "quote": None,
                "note": None,
            }

        other = {"text": "Ganz anderes Vorhaben ohne Demo."}
        assert _post(client, "/api/profile", other, 503)["code"] == "ki_nicht_verfuegbar"

    assert result["matches"] == stored["matches"]
    assert result["plan"] == stored["plan"]
    assert result["status"] == "fertig"
    assert result["run_id"] == run_id
    assert events[0]["type"] == "run_started"
    assert events[-1]["type"] == "run_completed"
    assert "instrument_completed" in [e["type"] for e in events]


def test_profile_before_answers():
    stored = json.loads(EXAMPLE.read_text(encoding="utf-8"))["profile"]
    profile = ProjectProfile.model_validate(stored)
    answered = [n for n, f in profile.fields.items() if f.origin == "rueckfrage"]
    assert answered, "the example run answers at least one question"
    before = profile_before_answers(profile)
    for name in answered:
        if name.startswith("rueckfrage_"):
            assert name not in before.fields
        else:
            assert before.fields[name].status == "fehlt"
    untouched = {n: f for n, f in profile.fields.items() if f.origin != "rueckfrage"}
    assert {n: before.fields[n] for n in untouched} == untouched
