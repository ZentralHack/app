from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _client(tmp_path, **settings) -> TestClient:
    (tmp_path / "index.html").write_text("<html>spa</html>")
    (tmp_path / "app.js").write_text("js")
    return TestClient(create_app(Settings(_env_file=None, frontend_dist=tmp_path, **settings)))


def test_serves_static_files_with_spa_fallback(tmp_path):
    with _client(tmp_path) as client:
        assert client.get("/app.js").text == "js"
        assert "spa" in client.get("/ergebnis/123").text
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/gibt-es-nicht").status_code == 404


def test_basic_auth_protects_site_and_api(tmp_path):
    with _client(tmp_path, basic_auth_user="u", basic_auth_password="p") as client:
        assert client.get("/").status_code == 401
        assert client.get("/api/health").status_code == 401
        assert client.get("/api/health", auth=("u", "p")).status_code == 200
        assert client.get("/", auth=("u", "x")).status_code == 401
