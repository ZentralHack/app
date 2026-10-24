/*
 * What a deadline means in plain words, derived in code from the deadline type and the rule the backend writes
 * (deadlines.py: knowledge-base wording, the cost-year note, or the problem when the project start is reached).
 * Never from the LLM.
 */
import type { Deadline } from "../api/contract";

/** Rule the backend writes for deadlines that follow the cost year (deadlines.py `cost_year_note`). */
export const COST_YEAR = /^Beitragsjahr (\d{4}), (bemessen auf Ihre Kosten im Geschäftsjahr \d{4})\.?$/;
/** Rule the backend writes when the project start is reached before the application (deadlines.py `before_start_rule`). */
export const START_REACHED = /^Projektstart liegt vor dem Gesuch\b/;
const EVENT = /\bvor (Installationsbeginn|Baubeginn|Projektbeginn|Projektstart)\b/;

export interface DeadlineInfo {
  /** What is due, e.g. "Gesuch vor Installationsbeginn einreichen". */
  label: string;
  /** A real date that is today or later, never one in the past. */
  date: string | null;
  /** E.g. "vor Ihrem Projektstart (12/2026)". */
  note: string | null;
  /** Shown instead of a date when the deadline cannot be met as planned. */
  problem: string | null;
}

export function deadlineInfo(deadline: Deadline, today: string): DeadlineInfo {
  const date = deadline.next_date && deadline.next_date >= today ? deadline.next_date : null;
  const rule = deadline.rule ?? "";
  const base = { date, note: null, problem: null };

  if (deadline.type === "vor_projektstart") {
    const event = rule.match(EVENT)?.[1] ?? "Projektstart";
    const label = `Gesuch vor ${event} einreichen`;
    if (START_REACHED.test(rule)) return { label, date: null, note: null, problem: rule };
    if (deadline.next_date && !date) return { label, date: null, note: null, problem: `Projektstart liegt vor dem Gesuch: Gesuch muss vor ${event} eingereicht werden.` };
    return { label, date, note: date ? `vor Ihrem Projektstart (${monthYear(date)})` : null, problem: null };
  }
  if (deadline.next_date && !date) return { label: "Eingabefrist Gesuch", date: null, note: null, problem: "Die Frist ist abgelaufen." };

  const costYear = rule.match(COST_YEAR);
  if (costYear) return { ...base, label: `Eingabefrist Gesuch Beitragsjahr ${costYear[1]}`, note: costYear[2] };
  switch (deadline.type) {
    case "laufend":
      return { ...base, label: "Gesuch jederzeit möglich" };
    case "ausschreibung":
      return { ...base, label: date ? "Nächste Ausschreibung schliesst" : "Gesuch im Rahmen einer Ausschreibung" };
    case "fester_termin":
    case "fester_termin_jaehrlich":
      return { ...base, label: date ? "Eingabefrist Gesuch" : "Keine nächste Frist bekannt" };
    case "nach_abschluss":
      return { ...base, label: "Unterlagen nach Projektabschluss einreichen" };
    default:
      return { ...base, label: "Frist nicht bekannt" };
  }
}

/** "2026-12-01" → "12/2026" */
function monthYear(iso: string): string {
  const [year, month] = iso.split("-");
  return `${month}/${year}`;
}
