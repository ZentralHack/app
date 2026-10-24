from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Header, Response
from fastapi.responses import StreamingResponse

from app.agent.answers import apply_answers
from app.agent.normalize import validate_profile
from app.agent.orchestrator import claim_retry, retry_instrument, run_analysis
from app.api.deps import (
    DemoDep,
    KnowledgeBaseDep,
    LLMDep,
    OptionalLLMDep,
    RunsDep,
    SettingsDep,
    require_llm,
)
from app.demo import replay
from app.models.contract import InstrumentRef, RetryRequest, RunCreated, RunRequest, RunResult
from app.trace import RunRecorder

router = APIRouter(prefix="/runs")


@router.post("", status_code=202)
async def start_run(
    req: RunRequest,
    kb: KnowledgeBaseDep,
    llm: OptionalLLMDep,
    runs: RunsDep,
    settings: SettingsDep,
    demo: DemoDep,
) -> RunCreated:
    """Applies the answers and starts steps 3 to 6 in the background (or a demo replay)."""
    validate_profile(req.profile, kb.criterion_questions)
    profile = apply_answers(req.profile, req.answers, kb)
    today = settings.today()
    case = demo.find(profile.input_text)
    if case is not None:
        recorder = runs.create(profile, today)
        runs.start(replay(case, recorder))
    else:
        live = require_llm(llm)
        recorder = runs.create(profile, today)
        runs.start(run_analysis(profile, kb, live, recorder, today))
    return RunCreated(run_id=recorder.run_id)


@router.get("/{run_id}")
def get_run(run_id: str, runs: RunsDep) -> RunResult:
    """Partial while `status` is `laeuft`."""
    return runs.get(run_id).result


@router.get("/{run_id}/events", response_class=StreamingResponse)
def run_events(
    run_id: str,
    runs: RunsDep,
    last_event_id: Annotated[int, Header(ge=0)] = 0,
) -> StreamingResponse:
    """Server-Sent Events. Replays everything after `Last-Event-ID`, then follows the run."""
    recorder = runs.get(run_id)
    return StreamingResponse(
        _sse(recorder, last_event_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _sse(recorder: RunRecorder, after: int) -> AsyncIterator[str]:
    async for event in recorder.events_after(after):
        body = event.root
        yield f"id: {body.seq}\nevent: {body.type}\ndata: {event.model_dump_json()}\n\n"


@router.post("/{run_id}/retry", status_code=202, response_class=Response)
async def retry(
    run_id: str,
    req: RetryRequest,
    kb: KnowledgeBaseDep,
    llm: LLMDep,
    runs: RunsDep,
    settings: SettingsDep,
) -> Response:
    """Re-checks one instrument with status `fehler`."""
    recorder = runs.get(run_id)
    ref = InstrumentRef(program_id=req.program_id, instrument_id=req.instrument_id)
    item = claim_retry(recorder, ref, kb)
    runs.start(retry_instrument(item, kb, llm, recorder, settings.today()))
    return Response(status_code=202)
