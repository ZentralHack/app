/* Derived views on a RunResult. Pure functions, no React. Ranking and fit levels come from the backend. */
import type { CriterionResult, InstrumentMatch, Rejected } from "../api/contract";
import type { Fit } from "../text/de-CH";

export type BadgeCounts = Record<"erfuellt" | "annahme" | "unbekannt" | "nicht_erfuellt", number>;

/** Matches with a fit level, sorted by backend rank. Failed checks are kept separately. */
export function splitMatches(matches: InstrumentMatch[]) {
  const byRank = (a: InstrumentMatch, b: InstrumentMatch) => (a.rank ?? Infinity) - (b.rank ?? Infinity);
  const ofFit = (fit: Fit) => matches.filter(m => m.status === "fertig" && m.fit === fit).sort(byRank);
  return {
    good: ofFit("passt_gut"),
    adapt: ofFit("passt_mit_anpassung"),
    notFit: ofFit("passt_nicht"),
    failed: matches.filter(m => m.status === "fehler"),
  };
}

/** Criteria shown on a card: applicable ones, worst state first. */
export function visibleCriteria(criteria: CriterionResult[]): CriterionResult[] {
  const order: Record<CriterionResult["state"], number> = { nicht_erfuellt: 0, unbekannt: 1, annahme: 2, erfuellt: 3, nicht_anwendbar: 4 };
  return criteria.filter(c => c.state !== "nicht_anwendbar").sort((a, b) => order[a.state] - order[b.state]);
}

export interface RejectedGroup {
  program_id: string;
  program_name: string;
  rule: Rejected["rule"];
  reason: string;
  instruments: Rejected[];
}

/** Groups pre-filter rejects with the same program, rule and reason, so 6 energy measures show as one row. */
export function groupRejected(rejected: Rejected[]): RejectedGroup[] {
  const groups = new Map<string, RejectedGroup>();
  for (const r of rejected) {
    const key = `${r.program_id}|${r.rule}|${r.reason}`;
    const g = groups.get(key) ?? { program_id: r.program_id, program_name: r.program_name, rule: r.rule, reason: r.reason, instruments: [] };
    g.instruments.push(r);
    groups.set(key, g);
  }
  return [...groups.values()];
}
