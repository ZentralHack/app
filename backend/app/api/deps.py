"""FastAPI dependencies: shared state set up at startup."""

from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings
from app.knowledge_base.loader import KnowledgeBase


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_kb(request: Request) -> KnowledgeBase:
    return request.app.state.kb


SettingsDep = Annotated[Settings, Depends(get_settings)]
KnowledgeBaseDep = Annotated[KnowledgeBase, Depends(get_kb)]
