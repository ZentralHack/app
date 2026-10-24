"""FastAPI app. Start from backend/:  uv run uvicorn app.main:app --reload"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, programs
from app.config import KNOWLEDGE_BASE_DIR, Settings, get_settings
from app.knowledge_base.loader import KnowledgeBase, load_knowledge_base


def create_app(settings: Settings | None = None, kb: KnowledgeBase | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.kb = kb or load_knowledge_base(KNOWLEDGE_BASE_DIR)
        yield

    app = FastAPI(title="Fördermittel-Agent", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (health, programs):
        app.include_router(module.router, prefix="/api")
    return app


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
app = create_app()
