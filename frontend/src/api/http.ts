/*
 * The Api against the FastAPI backend (design/api_contract.md). Requests go to /api; in development Vite
 * proxies them to the backend (vite.config.ts), so no CORS setup is needed.
 */
import type { Api } from "./client";
import type { ApiError, InstrumentRef, TraceEvent } from "./contract";

const BASE = "/api";

const EVENT_TYPES = [
  "run_started",
  "step_started",
  "step_completed",
  "prefilter_result",
  "instrument_started",
  "instrument_completed",
  "instrument_failed",
  "plan_ready",
  "run_completed",
  "run_failed",
] as const satisfies readonly TraceEvent["type"][];

const NETWORK_ERROR = "Der Server ist nicht erreichbar. Bitte prüfen Sie die Verbindung und versuchen Sie es nochmals.";
const UNKNOWN_ERROR = "Ein unerwarteter Fehler ist aufgetreten.";

/** A failed request. `message` is German and can be shown as is. */
export class ApiRequestError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(BASE + path, {
      method,
      headers: body === undefined ? undefined : { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiRequestError(0, "netzwerk", NETWORK_ERROR);
  }
  const text = await response.text();
  const data: unknown = text ? JSON.parse(text) : undefined;
  if (!response.ok) {
    const error = data as Partial<ApiError> | undefined;
    throw new ApiRequestError(response.status, error?.code ?? "http_fehler", error?.message ?? UNKNOWN_ERROR);
  }
  return data as T;
}

function chatPath(runId: string, ref: InstrumentRef): string {
  return `/runs/${encodeURIComponent(runId)}/chat/${encodeURIComponent(ref.program_id)}/${encodeURIComponent(ref.instrument_id)}`;
}

/**
 * One open event stream per run. The server replays all events on every connect, so events at or below
 * `lastSeq` are skipped. The stream is closed after the run ends, or after the plan of a retry; otherwise
 * EventSource would reconnect forever once the server closes an idle stream.
 */
interface Subscription {
  onEvent: (event: TraceEvent) => void;
  source: EventSource | null;
  lastSeq: number;
  retrying: boolean;
}

export function createHttpApi(): Api {
  const subscriptions = new Map<string, Subscription>();

  function connect(runId: string, sub: Subscription) {
    sub.source?.close();
    const source = new EventSource(`${BASE}/runs/${encodeURIComponent(runId)}/events`);
    sub.source = source;
    const handle = (message: MessageEvent<string>) => {
      const event = JSON.parse(message.data) as TraceEvent;
      if (event.seq <= sub.lastSeq) return;
      sub.lastSeq = event.seq;
      sub.onEvent(event);
      const done = event.type === "run_completed" || event.type === "run_failed" || (sub.retrying && event.type === "plan_ready");
      if (done) {
        source.close();
        sub.retrying = false;
      }
    };
    for (const type of EVENT_TYPES) source.addEventListener(type, handle);
  }

  return {
    listPrograms: () => request("GET", "/programs"),
    createProfile: req => request("POST", "/profile", req),
    buildQuestions: profile => request("POST", "/questions", { profile }),
    startRun: req => request("POST", "/runs", req),
    getRun: runId => request("GET", `/runs/${encodeURIComponent(runId)}`),
    chatSuggestions: (runId, ref) => request("GET", `${chatPath(runId, ref)}/suggestions`),
    chat: (runId, ref, req) => request("POST", chatPath(runId, ref), req),

    subscribeEvents(runId, onEvent) {
      const sub: Subscription = { onEvent, source: null, lastSeq: 0, retrying: false };
      subscriptions.set(runId, sub);
      connect(runId, sub);
      return () => {
        sub.source?.close();
        if (subscriptions.get(runId) === sub) subscriptions.delete(runId);
      };
    },

    async retryInstrument(runId, ref) {
      await request<void>("POST", `/runs/${encodeURIComponent(runId)}/retry`, ref);
      // The retry adds events to a stream that was already closed: listen again until its plan is ready.
      const sub = subscriptions.get(runId);
      if (sub) {
        sub.retrying = true;
        connect(runId, sub);
      }
    },
  };
}
