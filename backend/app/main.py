"""FastAPI app. Start from backend/:  uv run uvicorn app.main:app --reload"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, health, profile, programs, questions, runs
from app.api.errors import register_error_handlers
from app.config import DEMO_DIR, KNOWLEDGE_BASE_DIR, Settings, get_settings
from app.demo import DemoCases, load_demo_cases
from app.knowledge_base.loader import KnowledgeBase, load_knowledge_base
from app.llm.client import LLMClient
from app.llm.openai_client import OpenAIClient
from app.runs import RunStore


def create_app(
    settings: Settings | None = None,
    kb: KnowledgeBase | None = None,
    llm: LLMClient | None = None,
    demo: DemoCases | None = None,
) -> FastAPI:
    """`kb`, `llm` and `demo` can be passed in for tests; by default they come from the
    settings."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.kb = kb or load_knowledge_base(KNOWLEDGE_BASE_DIR)
        app.state.llm = llm or (OpenAIClient(settings) if settings.llm_configured else None)
        app.state.runs = RunStore(
            persist=settings.dev_runs_file if settings.dev_persist_runs else None
        )
        if demo is not None:
            app.state.demo = demo
        else:
            app.state.demo = load_demo_cases(DEMO_DIR) if settings.demo_replay else DemoCases()
        yield
        await app.state.runs.wait_idle()

    app = FastAPI(title="Fördermittel-Agent", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    for module in (health, programs, profile, questions, runs, chat):
        app.include_router(module.router, prefix="/api")
    return app


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
app = create_app()
