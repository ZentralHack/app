"""In-memory run store. Runs live as long as the process; the oldest are dropped first."""

import asyncio
import secrets
from collections import OrderedDict
from collections.abc import Coroutine
from datetime import date
from typing import Any

from app.agent.orchestrator import new_result
from app.models.contract import ProjectProfile
from app.trace import RunRecorder

MAX_RUNS = 200


class RunNotFoundError(KeyError):
    pass


class RunStore:
    def __init__(self, max_runs: int = MAX_RUNS) -> None:
        self._runs: OrderedDict[str, RunRecorder] = OrderedDict()
        self._tasks: set[asyncio.Task[Any]] = set()
        self._max_runs = max_runs

    def create(self, profile: ProjectProfile, today: date) -> RunRecorder:
        run_id = f"run_{secrets.token_hex(4)}"
        recorder = RunRecorder(run_id, new_result(run_id, profile, today))
        recorder.set_busy(True)  # until the run task finishes, so early SSE clients wait
        self._runs[run_id] = recorder
        while len(self._runs) > self._max_runs:
            self._runs.popitem(last=False)
        return recorder

    def get(self, run_id: str) -> RunRecorder:
        try:
            return self._runs[run_id]
        except KeyError:
            raise RunNotFoundError(run_id) from None

    def start(self, work: Coroutine[Any, Any, Any]) -> None:
        """Runs `work` in the background and keeps a reference until it is done."""
        task = asyncio.get_running_loop().create_task(work)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def wait_idle(self) -> None:
        """For tests and shutdown: wait until every background task is done."""
        while self._tasks:
            await asyncio.gather(*self._tasks)
