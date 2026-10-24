"""Runs steps 3 to 6 for one profile and records every step as a trace event.

A failing instrument check never stops the run: the instrument gets status `fehler`
and can be retried. Only an unexpected error in the orchestration itself fails the run.
"""

import asyncio
import logging
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.agent.deadlines import deadline, next_deadline
from app.agent.matching import check_instrument
from app.agent.plan import PlanItem, build_plan
from app.agent.plan_texts import write_plan_texts
from app.agent.prefilter import prefilter
from app.agent.questions import criterion_question
from app.agent.scoring import (
    RankEntry,
    assign_ranks,
    is_advisory,
    is_competitive,
    mostly_unknown,
    muss_met_share,
    score,
)
from app.agent.timing import apply_timing
from app.knowledge_base.flat import FlatInstrument
from app.knowledge_base.loader import KnowledgeBase
from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.llm.usage import current_usage
from app.models.contract import (
    InstrumentMatch,
    InstrumentMatchLinks,
    InstrumentRef,
    ProjectProfile,
    Rejected,
    RunResult,
)
from app.trace import RunRecorder

log = logging.getLogger(__name__)

DISCLAIMER = "Orientierungshilfe, keine verbindliche Beurteilung"
CHECK_FAILED = "Die Prüfung ist fehlgeschlagen."
FIT_LABELS = {
    "passt_gut": "passt gut",
    "passt_mit_anpassung": "passt mit Anpassung",
    "passt_nicht": "passt nicht",
}
BADGE_STATES = ("erfuellt", "annahme", "unbekannt", "nicht_erfuellt")


class RetryNotAllowedError(Exception):
    """The instrument is not in status `fehler` (HTTP 409)."""


@dataclass(frozen=True)
class _Context:
    profile: ProjectProfile
    kb: KnowledgeBase
    llm: LLMClient
    recorder: RunRecorder
    today: date


def new_result(run_id: str, profile: ProjectProfile, today: date) -> RunResult:
    return RunResult(
        run_id=run_id,
        status="laeuft",
        created_at=datetime.now(UTC),
        completed_at=None,
        today=today,
        disclaimer=DISCLAIMER,
        profile=profile,
        matches=[],
        rejected=[],
        plan=None,
        error=None,
    )


async def run_analysis(
    profile: ProjectProfile,
    kb: KnowledgeBase,
    llm: LLMClient,
    recorder: RunRecorder,
    today: date,
) -> RunResult:
    ctx = _Context(profile, kb, llm, recorder, today)
    token = current_usage.set(recorder.usage)
    started = time.monotonic()
    recorder.set_busy(True)
    try:
        await _analyse(ctx)
        _finish(ctx, started)
    except Exception:
        log.exception("Lauf %s abgebrochen", recorder.run_id)
        _fail(ctx)
    finally:
        current_usage.reset(token)
        recorder.set_busy(False)
        _log_run(recorder, started)
    return recorder.result


async def _analyse(ctx: _Context) -> None:
    recorder = ctx.recorder
    instruments = list(ctx.kb.instruments())
    recorder.emit(
        "run_started",
        f"Analyse gestartet: {len(instruments)} Förderangebote"
        f" aus {len(ctx.kb.programs)} Programmen.",
        {"programs": len(ctx.kb.programs), "instruments": len(instruments)},
    )

    with _step(recorder, "vorfilter", "Vorfilter läuft.", "Vorfilter fertig."):
        result = prefilter(ctx.profile, instruments)
        recorder.emit(
            "prefilter_result",
            f"{len(result.kept)} Förderangebote kommen in Frage,"
            f" {len(result.rejected)} passen nicht.",
            {
                "kept": [i.ref.model_dump() for i in result.kept],
                "rejected": [r.model_dump(mode="json") for r in result.rejected],
            },
        )
    _update(ctx, matches=[_pending(i, ctx) for i in result.kept], rejected=result.rejected)

    with _step(recorder, "pruefung", "Kriterien werden geprüft.", "Prüfung fertig."):
        await asyncio.gather(*(_check(ctx, item) for item in result.kept))

    with _step(recorder, "bewertung", "Bewertung läuft.", "Bewertung fertig."):
        _rank(ctx)

    with _step(recorder, "fahrplan", "Förderfahrplan wird erstellt.", "Fahrplan fertig."):
        await _plan(ctx)


def claim_retry(recorder: RunRecorder, ref: InstrumentRef, kb: KnowledgeBase) -> FlatInstrument:
    """Marks the run busy for a retry of one failed instrument, synchronously, so a second
    request cannot start the same retry. RetryNotAllowedError otherwise."""
    match = _find(recorder.result, ref)
    item = kb.find(ref)
    if match is None or match.status != "fehler" or recorder.busy or item is None:
        raise RetryNotAllowedError
    recorder.set_busy(True)
    return item


async def retry_instrument(
    item: FlatInstrument,
    kb: KnowledgeBase,
    llm: LLMClient,
    recorder: RunRecorder,
    today: date,
) -> RunResult:
    """Checks one failed instrument again (claimed with `claim_retry`), then ranks and
    plans anew."""
    ctx = _Context(recorder.result.profile, kb, llm, recorder, today)
    token = current_usage.set(recorder.usage)
    try:
        await _check(ctx, item)
        _rank(ctx)
        await _plan(ctx)
    except Exception:
        log.exception("Nochmals-Prüfung in Lauf %s abgebrochen", recorder.run_id)
        _fail(ctx)
    finally:
        current_usage.reset(token)
        recorder.set_busy(False)
    return recorder.result


async def _check(ctx: _Context, item: FlatInstrument) -> None:
    recorder = ctx.recorder
    ref = item.ref.model_dump()
    _set_match(ctx, item, status="laeuft", error=None)
    recorder.emit(
        "instrument_started",
        f"Prüfe {item.instrument.name}.",
        ref | {"program_name": item.program.name, "instrument_name": item.instrument.name},
    )
    started = time.monotonic()
    try:
        check = await check_instrument(item, ctx.profile, ctx.llm)
    except LLMError as error:
        _instrument_failed(ctx, item, error.message, error.retryable)
        return
    except Exception:
        log.exception("Prüfung von %s fehlgeschlagen", item.key)
        _instrument_failed(ctx, item, CHECK_FAILED, retryable=True)
        return
    recorder.downgrades += check.downgrades
    # Timing conditions the user can still meet are not open (see timing.py); scored after that.
    timed = [
        apply_timing(scoped.criterion, c, ctx.profile, ctx.today)
        for scoped, c in zip(item.criteria(), check.criteria, strict=True)
    ]
    scored = score(item, timed, bool(check.exclusion_hits), check.lever_texts)
    criteria = [
        c.model_copy(update={"question": criterion_question(item, scoped, ctx.kb, ctx.profile)})
        for scoped, c in zip(item.criteria(), timed, strict=True)
    ]
    _set_match(ctx, item, status="fertig", fit=scored.fit, criteria=criteria, gaps=scored.gaps)
    badges = Counter(c.state for c in timed)
    recorder.emit(
        "instrument_completed",
        f"{item.instrument.name}: {FIT_LABELS[scored.fit]}.",
        ref
        | {
            "fit": scored.fit,
            "badges": {state: badges[state] for state in BADGE_STATES},
            "duration_ms": _ms(started),
        },
    )


def _instrument_failed(ctx: _Context, item: FlatInstrument, message: str, retryable: bool) -> None:
    _set_match(ctx, item, status="fehler", fit=None, rank=None, criteria=[], gaps=[], error=message)
    ctx.recorder.emit(
        "instrument_failed",
        f"{item.instrument.name}: {message}",
        item.ref.model_dump() | {"error": message, "retryable": retryable},
    )


def _rank(ctx: _Context) -> None:
    result = ctx.recorder.result
    entries = []
    for match in result.matches:
        if match.fit is None:
            continue
        entries.append(
            RankEntry(
                _key(match),
                match.fit,
                muss_met_share(match.criteria),
                match.deadline.next_date,
                _item(ctx, match).program.entitlement.type,
                advisory=is_advisory(match.instrument_type),
                mostly_unknown=mostly_unknown(match.criteria),
                competitive=is_competitive(_item(ctx, match)),
            )
        )
    ranks = assign_ranks(entries)
    _update(
        ctx, matches=[m.model_copy(update={"rank": ranks.get(_key(m))}) for m in result.matches]
    )


async def _plan(ctx: _Context) -> None:
    result = ctx.recorder.result
    items = [
        PlanItem(
            _item(ctx, m),
            m.fit,
            m.gaps,
            next_deadline(_item(ctx, m), ctx.profile, ctx.today),
            m.deadline.rule,
        )
        for m in result.matches
        if m.fit is not None
    ]
    plan = build_plan(items, result.rejected, ctx.kb)
    fitting = [m for m in result.matches if m.fit is not None]
    plan, scored = await write_plan_texts(plan, fitting, ctx.kb, ctx.llm)
    texts = {_key(m): m for m in scored}
    _update(ctx, plan=plan, matches=[texts.get(_key(m), m) for m in result.matches])
    ctx.recorder.emit(
        "plan_ready",
        f"Fahrplan mit {len(plan.timeline)} Schritten erstellt.",
        {"timeline_entries": len(plan.timeline), "warnings": len(plan.warnings)},
    )


def _finish(ctx: _Context, started: float) -> None:
    result = ctx.recorder.result
    fits = Counter(m.fit for m in result.matches if m.fit)
    fits["passt_nicht"] += len(result.rejected)
    _update(ctx, status="fertig", completed_at=datetime.now(UTC))
    ctx.recorder.emit(
        "run_completed",
        "Analyse abgeschlossen.",
        {
            "duration_ms": _ms(started),
            "fits": {fit: fits[fit] for fit in FIT_LABELS},
        },
    )


def _fail(ctx: _Context) -> None:
    message = "Die Analyse ist abgebrochen. Bitte starten Sie sie nochmals."
    _update(ctx, status="fehler", completed_at=datetime.now(UTC), error=message)
    ctx.recorder.emit("run_failed", message, {"error": message})


def _pending(item: FlatInstrument, ctx: _Context) -> InstrumentMatch:
    links = item.instrument.links
    return InstrumentMatch(
        program_id=item.program.id,
        instrument_id=item.instrument.id,
        program_name=item.program.name,
        instrument_name=item.instrument.name,
        provider=item.program.provider.name,
        level=item.program.level,
        purpose=item.program.purpose,
        instrument_type=item.instrument.instrument_type,
        funding_summary=item.instrument.funding.summary,
        deadline=deadline(item, ctx.profile, ctx.today),
        links=InstrumentMatchLinks(info=links.info, apply=links.apply, form=links.form),
        source_checked=item.program.meta.last_verified,
        status="ausstehend",
        fit=None,
        rank=None,
        criteria=[],
        gaps=[],
        error=None,
    )


def _set_match(ctx: _Context, item: FlatInstrument, **changes: object) -> None:
    result = ctx.recorder.result
    matches = [m.model_copy(update=changes) if _key(m) == item.key else m for m in result.matches]
    _update(ctx, matches=matches)


def _update(ctx: _Context, **changes: object) -> None:
    ctx.recorder.update(ctx.recorder.result.model_copy(update=changes))


def _find(result: RunResult, ref: InstrumentRef) -> InstrumentMatch | None:
    key = f"{ref.program_id}:{ref.instrument_id}"
    return next((m for m in result.matches if _key(m) == key), None)


def _item(ctx: _Context, match: InstrumentMatch) -> FlatInstrument:
    item = ctx.kb.find(
        InstrumentRef(program_id=match.program_id, instrument_id=match.instrument_id)
    )
    assert item is not None, f"{_key(match)} fehlt in der Wissensbasis"
    return item


def _key(match: InstrumentMatch | Rejected) -> str:
    return f"{match.program_id}:{match.instrument_id}"


def _ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


@contextmanager
def _step(recorder: RunRecorder, step: str, start: str, done: str) -> Iterator[None]:
    """Emits step_started and, if the block succeeds, step_completed."""
    started = time.monotonic()
    recorder.emit("step_started", start, {"step": step})
    yield
    recorder.emit("step_completed", done, {"step": step, "duration_ms": _ms(started)})


def _log_run(recorder: RunRecorder, started: float) -> None:
    usage = recorder.usage
    log.info(
        "Lauf %s: dauer_ms=%d herabstufungen=%d aufrufe=%d tokens_in=%d tokens_out=%d "
        "kosten_usd=%.4f",
        recorder.run_id,
        _ms(started),
        recorder.downgrades,
        len(usage.calls),
        usage.input_tokens,
        usage.output_tokens,
        usage.cost_usd,
    )
