from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.knowledge_base.loader import InvalidFile, KnowledgeBase
from app.main import create_app


@pytest.fixture
def client(kb: KnowledgeBase) -> TestClient:
    settings = Settings(_env_file=None, openai_api_key=None)
    with TestClient(create_app(settings, kb)) as test_client:
        yield test_client


def test_health_without_llm(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "eingeschraenkt",
        "llm_available": False,
        "programs_loaded": 2,
        "programs_invalid": 0,
    }


def test_health_ok_with_llm_configured(kb: KnowledgeBase):
    settings = Settings(
        _env_file=None, openai_api_key="sk-test", model_extract="small", model_reason="main"
    )
    with TestClient(create_app(settings, kb)) as client:
        assert client.get("/api/health").json()["status"] == "ok"


def test_programs(client: TestClient):
    programs = {p["id"]: p for p in client.get("/api/programs").json()}
    assert set(programs) == {"lib", "foerderprogramm-energie-lu"}
    lib = programs["lib"]
    assert lib["valid"] is True
    assert lib["instruments"] == [{"id": "lib-beitrag", "name": "Luzerner Innovationsbeitrag"}]
    assert lib["last_verified"] == "2026-10-23"
    assert lib["errors"] == []


def test_programs_lists_invalid_files(kb: KnowledgeBase):
    error = "level: 'planet' is not one of"
    broken = InvalidFile(Path("kaputt.json"), "kaputt", None, None, [error])
    kb_with_invalid = replace(kb, invalid=[broken])
    with TestClient(create_app(Settings(_env_file=None), kb_with_invalid)) as client:
        programs = {p["id"]: p for p in client.get("/api/programs").json()}
        assert client.get("/api/health").json()["programs_invalid"] == 1
    assert programs["kaputt"]["valid"] is False
    assert programs["kaputt"]["name"] == "kaputt.json"
    assert programs["kaputt"]["errors"] == [error]
