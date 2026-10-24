"""Settings from the environment and backend/.env."""

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
KNOWLEDGE_BASE_DIR = REPO_DIR / "knowledge_base"
CONTRACT_SCHEMA = REPO_DIR / "design" / "contract.schema.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    openai_api_key: SecretStr | None = None
    llm_provider: Literal["openai"] = "openai"
    model_extract: str | None = None
    model_reason: str | None = None
    max_concurrency: int = 4
    llm_timeout_s: float = 30
    demo_today: date | None = None
    demo_replay: bool = False
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_configured(self) -> bool:
        """API key and both model ids are set. Says nothing about reachability."""
        return bool(self.openai_api_key and self.model_extract and self.model_reason)

    def today(self) -> date:
        """Reference date for all deadline logic: DEMO_TODAY if set, else today."""
        return self.demo_today or date.today()


@lru_cache
def get_settings() -> Settings:
    return Settings()
