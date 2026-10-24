import asyncio
from datetime import date

from app.runs import RunStore
from tests.factories import sensora_profile


async def _finish(store: RunStore, status: str = "fertig") -> str:
    recorder = store.create(sensora_profile(), date(2026, 10, 24))

    async def work() -> None:
        recorder.emit("run_started", "Start.", {"programs": 1, "instruments": 1})
        recorder.update(recorder.result.model_copy(update={"status": status}))
        recorder.set_busy(False)

    store.start(work(), recorder)
    await store.wait_idle()
    await asyncio.sleep(0)  # done callbacks run on the next loop turn
    return recorder.run_id


def test_finished_runs_survive_a_restart(tmp_path):
    path = tmp_path / "runs.json"
    run_id = asyncio.run(_finish(RunStore(persist=path)))
    again = RunStore(persist=path)
    loaded = again.get(run_id)
    assert loaded.result.status == "fertig"
    assert [e.root.type for e in loaded.events] == ["run_started"]
    assert not loaded.busy


def test_off_by_default_and_unfinished_runs_are_not_kept(tmp_path):
    path = tmp_path / "runs.json"
    asyncio.run(_finish(RunStore()))
    assert not path.exists()
    run_id = asyncio.run(_finish(RunStore(persist=path), status="fehler"))
    assert run_id not in RunStore(persist=path)._runs
