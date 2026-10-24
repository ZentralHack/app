import asyncio
from datetime import date

import pytest

from app.agent.orchestrator import new_result
from app.trace import RunRecorder
from tests.factories import sensora_profile


def _recorder() -> RunRecorder:
    return RunRecorder("run_test", new_result("run_test", sensora_profile(), date(2026, 10, 24)))


def test_live_client_follows_until_idle():
    async def scenario() -> list[int]:
        recorder = _recorder()
        recorder.set_busy(True)
        seen: list[int] = []

        async def client() -> None:
            async for event in recorder.events_after(0):
                seen.append(event.root.seq)

        task = asyncio.create_task(client())
        for step in ("vorfilter", "pruefung"):
            await asyncio.sleep(0)
            recorder.emit("step_started", "Schritt.", {"step": step})
        recorder.set_busy(False)
        await asyncio.wait_for(task, 1)
        return seen

    assert asyncio.run(scenario()) == [1, 2]


def test_events_are_validated_against_the_contract():
    async def scenario() -> None:
        _recorder().emit("step_started", "Schritt.", {"step": "gibt_es_nicht"})

    with pytest.raises(ValueError):
        asyncio.run(scenario())
