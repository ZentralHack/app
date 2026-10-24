/* The result counts shown on the trace and the results page. One function, so both screens always agree. */
import type { InstrumentMatch, RunResult } from "../api/contract";
import { isAdvisory, splitMatches } from "./results";

export interface ResultGroups {
  /** Money instruments, by backend rank. */
  good: InstrumentMatch[];
  adapt: InstrumentMatch[];
  /** Advice and coaching that fit (gut or mit Anpassung): "Begleitende Angebote". */
  advice: InstrumentMatch[];
  /** Checked in detail and passt nicht, plus everything the pre-filter dropped. */
  notFit: number;
  failed: InstrumentMatch[];
}

/** Every checked instrument lands in exactly one group, so nothing disappears from the counts. */
export function resultGroups(result: RunResult): ResultGroups {
  const split = splitMatches(result.matches);
  return {
    good: split.good.filter(m => !isAdvisory(m)),
    adapt: split.adapt.filter(m => !isAdvisory(m)),
    advice: [...split.good, ...split.adapt].filter(isAdvisory),
    notFit: split.notFit.length + result.rejected.length,
    failed: split.failed,
  };
}

export type SummaryTone = "ok" | "warn" | "neutral" | "error";

export interface SummaryPart {
  key: "good" | "adapt" | "advice" | "notFit" | "failed";
  n: number;
  tone: SummaryTone;
}

/** The groups in display order. Failed checks only appear when there are any. */
export function summaryParts(groups: ResultGroups): SummaryPart[] {
  const parts: SummaryPart[] = [
    { key: "good", n: groups.good.length, tone: "ok" },
    { key: "adapt", n: groups.adapt.length, tone: "warn" },
    { key: "advice", n: groups.advice.length, tone: "neutral" },
    { key: "notFit", n: groups.notFit, tone: "neutral" },
  ];
  if (groups.failed.length) parts.push({ key: "failed", n: groups.failed.length, tone: "error" });
  return parts;
}
