/* Folds the trace event stream into what the live panel shows. Pure function, replay-safe. */
import type { Rejected, TraceEvent } from "../api/contract";
import type { BadgeCounts } from "./results";
import type { Fit } from "../text/de-CH";

export type StepName = "vorfilter" | "pruefung" | "bewertung" | "fahrplan";
export type StageStatus = "wartet" | "laeuft" | "fertig";
export const STEP_ORDER: StepName[] = ["vorfilter", "pruefung", "bewertung", "fahrplan"];

export interface InstrumentLine {
  key: string;
  program_id: string;
  instrument_id: string;
  name: string;
  status: "laeuft" | "fertig" | "fehler";
  fit?: Fit;
  badges?: BadgeCounts;
  duration_ms?: number;
  error?: string;
  retryable?: boolean;
}

export interface TraceView {
  stages: Record<StepName, { status: StageStatus; duration_ms?: number }>;
  totals?: { programs: number; instruments: number };
  prefilter?: { kept: number; rejected: Rejected[] };
  instruments: InstrumentLine[];
  plan?: { timeline_entries: number; warnings: number };
  finished: boolean;
  failed?: string;
  duration_ms?: number;
}

export function traceView(events: TraceEvent[]): TraceView {
  const view: TraceView = {
    stages: { vorfilter: { status: "wartet" }, pruefung: { status: "wartet" }, bewertung: { status: "wartet" }, fahrplan: { status: "wartet" } },
    instruments: [],
    finished: false,
  };
  const line = (program_id: string, instrument_id: string) => view.instruments.find(l => l.key === `${program_id}:${instrument_id}`);

  for (const e of [...events].sort((a, b) => a.seq - b.seq)) {
    switch (e.type) {
      case "run_started":
        view.totals = e.data;
        break;
      case "step_started":
        view.stages[e.data.step] = { status: "laeuft" };
        break;
      case "step_completed":
        view.stages[e.data.step] = { status: "fertig", duration_ms: e.data.duration_ms };
        break;
      case "prefilter_result":
        view.prefilter = { kept: e.data.kept.length, rejected: e.data.rejected };
        break;
      case "instrument_started": {
        const key = `${e.data.program_id}:${e.data.instrument_id}`;
        const existing = line(e.data.program_id, e.data.instrument_id);
        const fresh: InstrumentLine = { key, program_id: e.data.program_id, instrument_id: e.data.instrument_id, name: e.data.instrument_name, status: "laeuft" };
        if (existing) Object.assign(existing, fresh, { error: undefined, retryable: undefined });
        else view.instruments.push(fresh);
        break;
      }
      case "instrument_completed": {
        const l = line(e.data.program_id, e.data.instrument_id);
        if (l) Object.assign(l, { status: "fertig", fit: e.data.fit, badges: e.data.badges, duration_ms: e.data.duration_ms });
        break;
      }
      case "instrument_failed": {
        const l = line(e.data.program_id, e.data.instrument_id);
        if (l) Object.assign(l, { status: "fehler", error: e.data.error, retryable: e.data.retryable });
        break;
      }
      case "plan_ready":
        view.plan = e.data;
        break;
      case "run_completed":
        view.finished = true;
        view.duration_ms = e.data.duration_ms;
        break;
      case "run_failed":
        view.finished = true;
        view.failed = e.data.error;
        break;
    }
  }
  return view;
}

/** Share of the four steps that are done, 0 to 1. */
export function progress(view: TraceView): number {
  return STEP_ORDER.filter(s => view.stages[s].status === "fertig").length / STEP_ORDER.length;
}
