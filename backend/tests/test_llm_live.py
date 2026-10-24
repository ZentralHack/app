"""Real calls against the configured provider. Off by default: uv run pytest -m live"""

import asyncio

import pytest

from app.config import get_settings
from app.llm.openai_client import OpenAIClient
from app.llm.schema import LLMOutput

pytestmark = pytest.mark.live


class Ping(LLMOutput):
    kanton: str


@pytest.mark.parametrize("tier", ["small", "main"])
def test_structured_call(tier):
    client = OpenAIClient(get_settings())
    result = asyncio.run(
        client.structured(
            task="live-test",
            system="Antworte nur mit dem verlangten Feld.",
            user="Kürzel des Kantons Luzern?",
            output=Ping,
            tier=tier,
            effort="low",
        )
    )
    assert result.kanton == "LU"
