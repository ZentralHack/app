import { describe, expect, it } from "vitest";
import type { RunResult, TraceEvent } from "../api/contract";
import pv from "../../../backend/demo/pv-schreinerei.json";
import sensora from "../../../backend/demo/sensor-prototyp.json";
import { isAdvisory } from "./results";
import { resultGroups, summaryParts } from "./summary";
import { traceView } from "./trace";

const cases: [string, RunResult][] = [
  ["Sensora", sensora as unknown as RunResult],
  ["PV-Schreinerei", pv as unknown as RunResult],
];

/** The events a replay of this result emits, enough for the trace view. */
function eventsOf(result: RunResult): TraceEvent[] {
  let seq = 0;
  const e = (type: string, data: unknown) => ({ seq: ++seq, type, ts: "2026-10-24T10:00:00Z", message: "", data }) as unknown as TraceEvent;
  const programs = new Set([...result.matches.map(m => m.program_id), ...result.rejected.map(r => r.program_id)]);
  return [
    e("run_started", { programs: programs.size, instruments: result.matches.length + result.rejected.length }),
    e("step_started", { step: "vorfilter" }),
    e("prefilter_result", { kept: result.matches.map(m => ({ program_id: m.program_id, instrument_id: m.instrument_id })), rejected: result.rejected }),
    e("step_completed", { step: "vorfilter", duration_ms: 1 }),
    e("step_started", { step: "pruefung" }),
    ...result.matches.flatMap(m => [
      e("instrument_started", { program_id: m.program_id, instrument_id: m.instrument_id, program_name: m.program_name, instrument_name: m.instrument_name }),
      e("instrument_completed", { program_id: m.program_id, instrument_id: m.instrument_id, fit: m.fit, badges: {}, duration_ms: 1 }),
    ]),
    e("step_completed", { step: "pruefung", duration_ms: 1 }),
    e("step_started", { step: "bewertung" }),
    e("step_completed", { step: "bewertung", duration_ms: 1 }),
  ];
}

describe.each(cases)("%s: counts", (_, result) => {
  it("put every checked instrument in exactly one group", () => {
    const g = resultGroups(result);
    expect(g.good.length + g.adapt.length + g.advice.length + g.notFit + g.failed.length).toBe(result.matches.length + result.rejected.length);
  });

  it("keep advice out of the money groups", () => {
    const g = resultGroups(result);
    expect([...g.good, ...g.adapt].some(isAdvisory)).toBe(false);
    expect(g.advice.every(isAdvisory)).toBe(true);
  });

  it("on the trace end state equal the counts on the results page", () => {
    const view = traceView(eventsOf(result));
    expect(view.stages.bewertung.status).toBe("fertig");
    // Per-instrument fits in the trace are final (bewertung only ranks), so they add up to the same groups.
    const fromTrace = view.instruments.reduce<Record<string, number>>((acc, l) => {
      const m = result.matches.find(x => x.program_id === l.program_id && x.instrument_id === l.instrument_id)!;
      const key = l.fit === "passt_nicht" ? "notFit" : isAdvisory(m) ? "advice" : l.fit === "passt_gut" ? "good" : "adapt";
      acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    }, {});
    const parts = Object.fromEntries(summaryParts(resultGroups(result)).map(p => [p.key, p.n]));
    expect(parts).toEqual({
      good: fromTrace.good ?? 0,
      adapt: fromTrace.adapt ?? 0,
      advice: fromTrace.advice ?? 0,
      notFit: (fromTrace.notFit ?? 0) + (view.prefilter?.rejected.length ?? 0),
    });
  });
});

it("Sensora: the numbers the results page shows", () => {
  const parts = summaryParts(resultGroups(sensora as unknown as RunResult)).map(p => [p.key, p.n]);
  expect(parts).toEqual([
    ["good", 1],
    ["adapt", 5],
    ["advice", 2],
    ["notFit", 29],
  ]);
});
