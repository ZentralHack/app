"""In-memory run store. Runs live as long as the process; the oldest are dropped first.

For development only (DEV_PERSIST_RUNS=true): finished runs are also written to a local file
outside the repository and loaded again on startup, so a backend restart keeps them.
"""

import asyncio
import json
import logging
import secrets
from collections import OrderedDict
from collections.abc import Coroutine
from datetime import date
from pathlib import Path
from typing import Any

from app.agent.orchestrator import new_result
from app.models.contract import ProjectProfile, RunResult, TraceEvent
from app.trace import RunRecorder

log = logging.getLogger(__name__)

MAX_RUNS = 200


class RunNotFoundError(KeyError):
    pass


class RunStore:
    def __init__(self, max_runs: int = MAX_RUNS, persist: Path | None = None) -> None:
        self._runs: OrderedDict[str, RunRecorder] = OrderedDict()
        self._tasks: set[asyncio.Task[Any]] = set()
        self._max_runs = max_runs
        self._persist = persist
        if persist is not None:
            self._load(persist)

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

    def start(self, work: Coroutine[Any, Any, Any], recorder: RunRecorder | None = None) -> None:
        """Runs `work` in the background and keeps a reference until it is done. With
        persistence on, the recorder's run is saved when the work is done."""
        task = asyncio.get_running_loop().create_task(work)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        if recorder is not None and self._persist is not None:
            task.add_done_callback(lambda _: self._save(recorder))

    def _save(self, recorder: RunRecorder) -> None:
        if recorder.result.status != "fertig" or self._persist is None:
            return
        stored = self._read(self._persist)
        stored.pop(recorder.run_id, None)
        stored[recorder.run_id] = {
            "result": recorder.result.model_dump(mode="json"),
            "events": [e.model_dump(mode="json") for e in recorder.events],
        }
        kept = dict(list(stored.items())[-self._max_runs :])
        self._persist.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._persist.with_suffix(".tmp")
        tmp.write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._persist)

    def _load(self, path: Path) -> None:
        for run_id, entry in self._read(path).items():
            try:
                recorder = RunRecorder(run_id, RunResult.model_validate(entry["result"]))
                recorder.events = [TraceEvent.model_validate(e) for e in entry["events"]]
            except (KeyError, ValueError) as error:
                log.warning("Gespeicherter Lauf %s nicht lesbar: %s", run_id, error)
                continue
            self._runs[run_id] = recorder
        if self._runs:
            log.info("%d gespeicherte Läufe geladen aus %s", len(self._runs), path)

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            log.warning("Lauf-Datei %s nicht lesbar, wird neu angelegt", path)
            return {}

    async def wait_idle(self) -> None:
        """For tests and shutdown: wait until every background task is done."""
        while self._tasks:
            await asyncio.gather(*self._tasks)
