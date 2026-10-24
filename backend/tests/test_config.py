from datetime import date

from app.config import Settings


def test_defaults_without_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "openai"
    assert settings.max_concurrency == 4
    assert settings.llm_timeout_s == 30
    assert settings.demo_replay is False
    assert settings.cors_origin_list == ["http://localhost:5173"]
    assert settings.llm_configured is False


def test_demo_today_overrides_today():
    settings = Settings(_env_file=None, demo_today=date(2026, 10, 23))
    assert settings.today() == date(2026, 10, 23)


def test_llm_configured_needs_key_and_both_models():
    settings = Settings(_env_file=None, openai_api_key="sk-test", model_extract="small")
    assert settings.llm_configured is False
    settings = Settings(
        _env_file=None, openai_api_key="sk-test", model_extract="small", model_reason="main"
    )
    assert settings.llm_configured is True


def test_cors_origins_comma_separated():
    settings = Settings(_env_file=None, cors_origins="http://a.test, http://b.test")
    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]


def test_empty_values_from_the_template_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("MAX_CONCURRENCY", "")
    monkeypatch.setenv("DEMO_TODAY", "")
    settings = Settings(_env_file=None)
    assert settings.max_concurrency == 4
    assert settings.demo_today is None
