"""DEMO_REPLAY: stored real results (backend/demo/*.json, written by the eval runner)
are played back with realistic delays, so the pitch works without API or network.

A demo case is found by its input text. Answers and profile corrections do not change a
replayed result; anything that is not a demo case runs live as usual. The profile is handed
out as it was before the answers, so the Rückfragen screen shows the same questions.
"""

import asyncio
import json
import logging
import random
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from app.agent.orchestrator import BADGE_STATES, FIT_LABELS
from app.agent.text import squash
from app.knowledge_base.questions import RUECKFRAGE
from app.models.contract import ProfileField, ProjectProfile, RunResult
from app.trace import RunRecorder

log = logging.getLogger(__name__)

# Seconds, roughly as measured with the real models (see eval runs).
STEP_DELAY_S = 0.3
CHECK_DELAY_S = (4.0, 12.0)
PLAN_DELAY_S = 4.0


@dataclass(frozen=True)
class DemoCases:
    by_text: dict[str, RunResult] = field(default_factory=dict)

    def find(self, text: str) -> RunResult | None:
        return self.by_text.get(squash(text))


def load_demo_cases(directory: Path) -> DemoCases:
    cases = {}
    for path in sorted(directory.glob("*.json")):
        try:
            result = RunResult.model_validate_json(path.read_bytes())
        except (OSError, ValidationError, json.JSONDecodeError) as error:
            log.error("Demo-Fall übersprungen: %s: %s", path.name, error)
            continue
        cases[squash(result.profile.input_text)] = result
    log.info("%d Demo-Fälle geladen", len(cases))
    return DemoCases(cases)


def profile_before_answers(profile: ProjectProfile) -> ProjectProfile:
    """The stored profile without what the Rückfragen added: answered profile fields go back to
    `fehlt`, answers to criterion questions (`rueckfrage_*`) are dropped."""
    missing = ProfileField(value=None, status="fehlt", origin=None, quote=None, note=None)
    fields = {}
    for name, value in profile.fields.items():
        if value.origin != "rueckfrage":
            fields[name] = value
        elif not name.startswith(RUECKFRAGE):
            fields[name] = missing
    return profile.model_copy(update={"fields": fields})


async def replay(
    case: RunResult,
    recorder: RunRecorder,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> RunResult:
    """Emits the same events as a live run, with the stored result."""
    recorder.set_busy(True)
    try:
        await _replay(case, recorder, sleep)
    finally:
        recorder.set_busy(False)
    return recorder.result


async def _replay(case: RunResult, recorder: RunRecorder, sleep) -> None:
    emit = recorder.emit
    recorder.update(
        recorder.result.model_copy(update={"profile": case.profile, "today": case.today})
    )
    programs = {m.program_id for m in case.matches} | {r.program_id for r in case.rejected}
    total = len(case.matches) + len(case.rejected)
    emit(
        "run_started",
        f"Analyse gestartet: {len(programs)} Programme, {total} Instrumente.",
        {"programs": len(programs), "instruments": total},
    )
    emit("step_started", "Vorfilter läuft.", {"step": "vorfilter"})
    await sleep(STEP_DELAY_S)
    emit(
        "prefilter_result",
        f"{len(case.matches)} Instrumente bleiben, {len(case.rejected)} passen nicht.",
        {
            "kept": [
                {"program_id": m.program_id, "instrument_id": m.instrument_id} for m in case.matches
            ],
            "rejected": [r.model_dump(mode="json") for r in case.rejected],
        },
    )
    emit("step_completed", "Vorfilter fertig.", {"step": "vorfilter", "duration_ms": 12})
    recorder.update(recorder.result.model_copy(update={"rejected": case.rejected}))

    emit("step_started", "Kriterien werden geprüft.", {"step": "pruefung"})
    rng = random.Random(case.run_id)  # same rhythm for the same case
    await asyncio.gather(
        *(_check(m, recorder, sleep, rng.uniform(*CHECK_DELAY_S)) for m in case.matches)
    )
    emit("step_completed", "Prüfung fertig.", {"step": "pruefung", "duration_ms": 0})
    emit("step_started", "Bewertung läuft.", {"step": "bewertung"})
    emit("step_completed", "Bewertung fertig.", {"step": "bewertung", "duration_ms": 3})

    emit("step_started", "Förderfahrplan wird erstellt.", {"step": "fahrplan"})
    await sleep(PLAN_DELAY_S)
    plan = case.plan
    recorder.update(recorder.result.model_copy(update={"matches": case.matches, "plan": plan}))
    timeline = len(plan.timeline) if plan else 0
    warnings = len(plan.warnings) if plan else 0
    emit(
        "plan_ready",
        f"Fahrplan mit {timeline} Schritten erstellt.",
        {"timeline_entries": timeline, "warnings": warnings},
    )
    emit("step_completed", "Fahrplan fertig.", {"step": "fahrplan", "duration_ms": 0})

    recorder.update(
        recorder.result.model_copy(update={"status": "fertig", "completed_at": datetime.now(UTC)})
    )
    fits = Counter(m.fit for m in case.matches if m.fit)
    fits["passt_nicht"] += len(case.rejected)
    emit(
        "run_completed",
        "Analyse abgeschlossen.",
        {"duration_ms": 0, "fits": {fit: fits[fit] for fit in FIT_LABELS}},
    )


async def _check(match, recorder: RunRecorder, sleep, delay: float) -> None:
    ref = {"program_id": match.program_id, "instrument_id": match.instrument_id}
    recorder.emit(
        "instrument_started",
        f"Prüfe {match.instrument_name}.",
        ref | {"program_name": match.program_name, "instrument_name": match.instrument_name},
    )
    await sleep(delay)
    if match.fit is None:
        recorder.emit(
            "instrument_failed",
            f"{match.instrument_name}: {match.error}",
            ref | {"error": match.error or "", "retryable": False},
        )
        return
    badges = Counter(c.state for c in match.criteria)
    recorder.emit(
        "instrument_completed",
        f"{match.instrument_name}: {FIT_LABELS[match.fit]}.",
        ref
        | {
            "fit": match.fit,
            "badges": {state: badges[state] for state in BADGE_STATES},
            "duration_ms": round(delay * 1000),
        },
    )
