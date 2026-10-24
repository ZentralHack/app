"""Per-run trace: numbered events for the live panel and the latest result.

The agent calls `emit` and `update`; the SSE endpoint reads with `events_after`.
Every event is validated against the contract when it is created.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from app.llm.usage import Usage
from app.models.contract import RunResult, TraceEvent


class RunRecorder:
    def __init__(self, run_id: str, result: RunResult) -> None:
        self.run_id = run_id
        self.result = result
        self.events: list[TraceEvent] = []
        self.downgrades = 0  # evidence-rule downgrades across all checks of this run
        self.usage = Usage()  # LLM calls of this run, incl. retries
        self._busy = False
        self._wake = asyncio.Event()

    @property
    def busy(self) -> bool:
        """A run or retry is working on this result."""
        return self._busy

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._notify()

    def emit(self, type_: str, message: str, data: dict[str, Any]) -> TraceEvent:
        event = TraceEvent.model_validate(
            {
                "run_id": self.run_id,
                "seq": len(self.events) + 1,
                "ts": datetime.now(UTC),
                "type": type_,
                "message": message,
                "data": data,
            }
        )
        self.events.append(event)
        self._notify()
        return event

    def update(self, result: RunResult) -> None:
        self.result = result

    def _notify(self) -> None:
        self._wake.set()
        self._wake = asyncio.Event()

    async def events_after(self, seq: int) -> AsyncIterator[TraceEvent]:
        """Replays events after `seq`, then follows new ones until the run is idle."""
        cursor = seq
        while True:
            wake = self._wake
            pending = self.events[cursor:]
            for event in pending:
                yield event
            cursor += len(pending)
            if cursor >= len(self.events):
                if not self._busy:
                    return
                await wake.wait()
