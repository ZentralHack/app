import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiRequestError } from "../api";
import type { RetryRequest, RunResult, TraceEvent } from "../api/contract";
import { traceView } from "../lib/trace";

/** Events after which the run result has new content worth fetching. */
const REFRESH_ON = new Set<TraceEvent["type"]>(["prefilter_result", "instrument_completed", "instrument_failed", "plan_ready", "run_completed", "run_failed"]);

const message = (e: unknown) => (e instanceof ApiRequestError ? e.message : "Die Analyse konnte nicht geladen werden.");

/** Live state of one analysis run: the trace events (SSE), the latest RunResult and the last request error. */
export function useRun(runId: string | null) {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEvents([]);
    setResult(null);
    setError(null);
    if (!runId) return;
    let active = true;
    const refresh = () =>
      api.getRun(runId).then(
        r => active && setResult(r),
        e => active && setError(message(e)),
      );
    const unsubscribe = api.subscribeEvents(runId, event => {
      if (!active) return;
      // Replays after a reconnect can repeat events; seq makes them idempotent.
      setEvents(prev => (prev.some(p => p.seq === event.seq) ? prev : [...prev, event]));
      if (REFRESH_ON.has(event.type)) void refresh();
    });
    void refresh();
    return () => {
      active = false;
      unsubscribe();
    };
  }, [runId]);

  const view = useMemo(() => traceView(events), [events]);
  const retry = useCallback(
    (ref: RetryRequest) => {
      if (!runId) return;
      setError(null);
      api.retryInstrument(runId, ref).catch(e => setError(message(e)));
    },
    [runId],
  );

  return { view, result, error, retry };
}
