import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiRequestError } from "../api";
import type { RetryRequest, RunResult, TraceEvent } from "../api/contract";
import { traceView } from "../lib/trace";

/** Events after which the run result has new content worth fetching. */
const REFRESH_ON = new Set<TraceEvent["type"]>(["prefilter_result", "instrument_completed", "instrument_failed", "step_completed", "plan_ready", "run_completed", "run_failed"]);

const message = (e: unknown) => (e instanceof ApiRequestError ? e.message : "Die Analyse konnte nicht geladen werden.");

interface RunData {
  events: TraceEvent[];
  result: RunResult | null;
  error: string | null;
}

const EMPTY: RunData = { events: [], result: null, error: null };

/**
 * Last known state per run id. When the shown run switches to a run that was followed in the
 * background, its data is there at once, so the page never flashes empty.
 */
const cache = new Map<string, RunData>();

/** Live state of one analysis run: the trace events (SSE), the latest RunResult and the last request error. */
export function useRun(runId: string | null) {
  const [state, setState] = useState<{ id: string | null } & RunData>({ id: runId, ...((runId && cache.get(runId)) || EMPTY) });

  useEffect(() => {
    setState({ id: runId, ...((runId && cache.get(runId)) || EMPTY) });
    if (!runId) return;
    let active = true;
    const patch = (update: (d: RunData) => RunData) =>
      setState(prev => {
        if (!active || prev.id !== runId) return prev;
        const next = update(prev);
        cache.set(runId, { events: next.events, result: next.result, error: next.error });
        return { ...next, id: runId };
      });
    const refresh = () =>
      api.getRun(runId).then(
        r => patch(d => ({ ...d, result: r })),
        e => patch(d => ({ ...d, error: message(e) })),
      );
    const unsubscribe = api.subscribeEvents(runId, event => {
      // Replays after a reconnect can repeat events; seq makes them idempotent.
      patch(d => (d.events.some(p => p.seq === event.seq) ? d : { ...d, events: [...d.events, event] }));
      if (REFRESH_ON.has(event.type)) void refresh();
    });
    void refresh();
    return () => {
      active = false;
      unsubscribe();
    };
  }, [runId]);

  // Until the effect has switched to the new id, show what is known about it (cache) rather than the old run.
  const data = state.id === runId ? state : (runId && cache.get(runId)) || EMPTY;
  const view = useMemo(() => traceView(data.events), [data.events]);
  const retry = useCallback(
    (ref: RetryRequest) => {
      if (!runId) return;
      setState(prev => ({ ...prev, error: null }));
      api.retryInstrument(runId, ref).catch(e => setState(prev => (prev.id === runId ? { ...prev, error: message(e) } : prev)));
    },
    [runId],
  );

  return { view, result: data.result, error: data.error, retry };
}
