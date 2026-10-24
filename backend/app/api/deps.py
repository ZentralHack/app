"""FastAPI dependencies: shared state set up at startup."""

from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings
from app.demo import DemoCases
from app.knowledge_base.loader import KnowledgeBase
from app.llm.client import LLMClient
from app.llm.errors import LLMUnavailableError
from app.runs import RunStore


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_kb(request: Request) -> KnowledgeBase:
    return request.app.state.kb


def require_llm(llm: LLMClient | None) -> LLMClient:
    if llm is None:
        raise LLMUnavailableError(
            "Die KI ist nicht konfiguriert (API-Schlüssel oder Modell fehlt).", retryable=False
        )
    return llm


def get_llm(request: Request) -> LLMClient:
    return require_llm(request.app.state.llm)


def get_optional_llm(request: Request) -> LLMClient | None:
    """For routes that can answer from DEMO_REPLAY without a model."""
    return request.app.state.llm


def get_demo(request: Request) -> DemoCases:
    return request.app.state.demo


def get_runs(request: Request) -> RunStore:
    return request.app.state.runs


SettingsDep = Annotated[Settings, Depends(get_settings)]
KnowledgeBaseDep = Annotated[KnowledgeBase, Depends(get_kb)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]
OptionalLLMDep = Annotated[LLMClient | None, Depends(get_optional_llm)]
DemoDep = Annotated[DemoCases, Depends(get_demo)]
RunsDep = Annotated[RunStore, Depends(get_runs)]
