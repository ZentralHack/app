/* Small building blocks shared by the results dashboard and the program dashboard. */
import type { ReactNode } from "react";
import type { CriterionResult, Deadline, SourceLink } from "../../api/contract";
import { daysUntil, formatDateShort } from "../../lib/format";
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

/** Rule the backend writes for deadlines that follow the cost year (deadlines.py `cost_year_note`). */
export const COST_YEAR = /^Beitragsjahr \d{4}, bemessen auf Ihre Kosten im Geschäftsjahr \d{4}\.?$/;

/** "31.01.2027" with "in 99 Tagen", or a short rule such as "Laufend". */
export function deadlineText(deadline: Deadline, today: string): { main: string; sub: string | null; urgency: Urgency } {
  if (deadline.next_date && deadline.rule && COST_YEAR.test(deadline.rule)) {
    // A claim on past costs (LIB): the line explains the year; no urgency colour.
    return { main: formatDateShort(deadline.next_date), sub: deadline.rule.replace(/\.$/, ""), urgency: "normal" };
  }
  if (deadline.next_date) {
    const days = daysUntil(deadline.next_date, today);
    return { main: formatDateShort(deadline.next_date), sub: t.results.inDays(days), urgency: urgencyOf(days) };
  }
  const label: Partial<Record<Deadline["type"], string>> = {
    laufend: "Laufend",
    vor_projektstart: "Vor Projektstart",
    nach_abschluss: "Nach Abschluss",
    ausschreibung: "Nach Ausschreibung",
  };
  return { main: label[deadline.type] ?? t.results.noDeadline, sub: null, urgency: "normal" };
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
  return (
    <span className="flex flex-col">
      <span className={`${size === "hero" ? "text-4xl" : "text-xl"} font-semibold tracking-tight tabular-nums ${URGENCY_TEXT[d.urgency]}`}>{d.main}</span>
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
