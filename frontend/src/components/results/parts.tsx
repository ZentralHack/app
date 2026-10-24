/* Small building blocks shared by the results dashboard and the program dashboard. */
import type { ReactNode } from "react";
import type { CriterionResult, Deadline, SourceLink } from "../../api/contract";
import { daysUntil, formatDateShort } from "../../lib/format";
import { COST_YEAR, deadlineInfo } from "../../lib/deadline";
import { visibleCriteria } from "../../lib/results";
import { STATE_LABEL, t } from "../../text/de-CH";

const BAR_COLOR: Record<CriterionResult["state"], string> = {
  erfuellt: "bg-ok",
  annahme: "bg-warn",
  unbekannt: "bg-line-strong",
  nicht_erfuellt: "bg-error",
  nicht_anwendbar: "bg-line",
};

/** One segment per criterion, best first: reads as "how much is already met". */
export function CriteriaBar({ criteria }: { criteria: CriterionResult[] }) {
  const list = [...visibleCriteria(criteria)].reverse();
  const met = list.filter(c => c.state === "erfuellt").length;
  return (
    <span className="inline-flex items-center gap-2" aria-label={`${met} von ${list.length} Kriterien erfüllt`}>
      <span aria-hidden="true" className="flex gap-0.5">
        {list.map(c => (
          <span key={c.criterion_id} title={STATE_LABEL[c.state]} className={`h-2 w-3.5 rounded-full ${BAR_COLOR[c.state]}`} />
        ))}
      </span>
      <span className="text-sm font-semibold tabular-nums">
        {met}/{list.length}
      </span>
    </span>
  );
}

export type Urgency = "normal" | "bald" | "dringend";

/** Deadline colour: neutral, amber under 30 days, red under 7. */
export const URGENCY_TEXT: Record<Urgency, string> = { normal: "text-fg", bald: "text-warn", dringend: "text-error" };

export function urgencyOf(days: number | null): Urgency {
  if (days === null || days < 0) return "normal";
  return days < 7 ? "dringend" : days < 30 ? "bald" : "normal";
}

/**
 * "31.01.2027" with what is due and "in 99 Tagen"; without a date what is due ("Gesuch jederzeit möglich");
 * a past date never shows: the problem replaces it.
 */
export function deadlineText(deadline: Deadline, today: string): { main: string; sub: string | null; urgency: Urgency; problem: boolean } {
  const info = deadlineInfo(deadline, today);
  if (info.problem) return { main: info.problem, sub: info.label, urgency: "bald", problem: true };
  if (!info.date) return { main: info.label, sub: null, urgency: "normal", problem: false };
  const days = daysUntil(info.date, today);
  // A claim on past costs (LIB) has a date years ahead: no countdown, no urgency colour.
  const costYear = COST_YEAR.test(deadline.rule ?? "");
  return {
    main: formatDateShort(info.date),
    sub: [info.label, info.note, costYear ? null : t.results.inDays(days)].filter(Boolean).join(" · "),
    urgency: costYear ? "normal" : urgencyOf(days),
    problem: false,
  };
}

/** Small muted label above a value. */
export function Metric({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={`flex min-w-0 flex-col gap-1 ${className}`}>
      <span className="text-xs font-semibold tracking-wide text-fg-2">{label}</span>
      {children}
    </div>
  );
}

/** Deadline as a figure with urgency colour. */
export function DeadlineFigure({ deadline, today, size = "card" }: { deadline: Deadline; today: string; size?: "hero" | "card" }) {
  const d = deadlineText(deadline, today);
  if (d.problem)
    return (
      <span className="flex max-w-[28em] flex-col gap-0.5" data-testid="deadline-problem">
        <span className={`${size === "hero" ? "text-lg" : "text-base"} font-semibold text-warn`}>{d.main}</span>
      </span>
    );
  const big = d.main.length <= 10; // a date; a label ("Gesuch jederzeit möglich") is set smaller
  return (
    <span className="flex flex-col">
      <span className={`${size === "hero" ? (big ? "text-4xl" : "text-2xl") : big ? "text-xl" : "text-base"} font-semibold tracking-tight tabular-nums ${URGENCY_TEXT[d.urgency]}`}>{d.main}</span>
      {d.sub && <span className={`text-sm ${d.urgency === "normal" ? "text-fg-2" : URGENCY_TEXT[d.urgency]}`}>{d.sub}</span>}
    </span>
  );
}

/** Numbered source chip. */
export function SourceChip({ source, n }: { source: SourceLink; n?: number }) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener"
      title={`${source.title}${source.locator ? ` · ${source.locator}` : ""}`}
      className="inline-flex h-7 max-w-full items-center gap-1.5 rounded-md border border-line bg-surface px-2 text-xs font-medium text-fg-2 no-underline transition-colors hover:border-primary hover:bg-primary-soft hover:text-primary-ink"
    >
      {n != null && <span className="grid size-4 flex-none place-items-center rounded bg-primary-soft text-[11px] font-bold text-primary-ink">{n}</span>}
      <span className="truncate">
        {source.title}
        {source.locator && ` · ${source.locator}`}
      </span>
    </a>
  );
}

/** Height-animated disclosure body. */
export function Collapse({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <div className={`grid transition-[grid-template-rows] duration-300 ease-(--ease-app) ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
      <div className="overflow-hidden">{children}</div>
    </div>
  );
}
