"""One tiny real call per model tier, to check key, model ids and structured outputs.

    uv run python -m scripts.llm_smoke

Reads backend/.env through the settings. Prints model, duration, tokens and cost only.
"""

import asyncio
import sys
import time

from app.config import get_settings
from app.llm.client import Tier
from app.llm.errors import LLMError
from app.llm.openai_client import OpenAIClient
from app.llm.schema import LLMOutput


class Ping(LLMOutput):
    kanton: str
    gemeinden: list[str]


async def _ping(client: OpenAIClient, tier: Tier) -> str:
    started = time.monotonic()
    result = await client.structured(
        task="smoke",
        system="Antworte knapp und nur mit den verlangten Feldern.",
        user="Kürzel des Kantons Luzern und zwei Gemeinden darin.",
        output=Ping,
        tier=tier,
        effort="low",
    )
    return f"{tier}: ok in {time.monotonic() - started:.1f}s, {result.kanton}, {result.gemeinden}"


async def main() -> int:
    try:
        client = OpenAIClient(get_settings())
        for tier in ("small", "main"):
            print(await _ping(client, tier))
    except LLMError as error:
        print(f"Fehler: {error.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(asyncio.run(main()))
