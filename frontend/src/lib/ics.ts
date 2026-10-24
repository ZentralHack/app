/*
 * Calendar files (RFC 5545), generated in the browser: all-day events with reminders 14 and 3 days before.
 * CRLF line ends, text escaped, lines folded at 75 bytes without splitting a UTF-8 character.
 */
import type { InstrumentMatch, RunResult } from "../api/contract";
import { deadlineInfo } from "./deadline";

export const DISCLAIMER = "Orientierungshilfe, keine verbindliche Beurteilung";

export interface CalendarEvent {
  uid: string;
  /** ISO date of the all-day event. */
  date: string;
  title: string;
  description: string;
  url: string | null;
}

export function escapeText(text: string): string {
  return text.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
}

/** Splits a content line into chunks of at most 75 bytes; continuation lines start with a space. */
export function foldLine(line: string): string {
  const encoder = new TextEncoder();
  const parts: string[] = [];
  let current = "";
  let bytes = 0;
  for (const char of line) {
    const size = encoder.encode(char).length;
    const limit = parts.length === 0 ? 75 : 74; // the leading space counts
    if (bytes + size > limit) {
      parts.push(current);
      current = "";
      bytes = 0;
    }
    current += char;
    bytes += size;
  }
  parts.push(current);
  return parts.join("\r\n ");
}

const compact = (iso: string) => iso.replace(/-/g, "");

function nextDay(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

function stamp(now: Date): string {
  return now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

function alarm(days: number, title: string): string[] {
  return ["BEGIN:VALARM", "ACTION:DISPLAY", `DESCRIPTION:${escapeText(title)}`, `TRIGGER:-P${days}D`, "END:VALARM"];
}

export function icsCalendar(events: CalendarEvent[], now: Date = new Date()): string {
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//FundPilot//Foerderfahrplan//DE", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"];
  for (const e of events) {
    lines.push(
      "BEGIN:VEVENT",
      `UID:${e.uid}`,
      `DTSTAMP:${stamp(now)}`,
      `DTSTART;VALUE=DATE:${compact(e.date)}`,
      `DTEND;VALUE=DATE:${compact(nextDay(e.date))}`,
      `SUMMARY:${escapeText(e.title)}`,
      `DESCRIPTION:${escapeText(e.description)}`,
      ...(e.url ? [`URL:${e.url}`] : []),
      "TRANSP:TRANSPARENT",
      ...alarm(14, e.title),
      ...alarm(3, e.title),
      "END:VEVENT",
    );
  }
  lines.push("END:VCALENDAR");
  return lines.map(foldLine).join("\r\n") + "\r\n";
}

/** The deadline of one offer as an event, or null without a real future date. */
export function deadlineEvent(match: InstrumentMatch, result: RunResult): CalendarEvent | null {
  const info = deadlineInfo(match.deadline, result.today);
  if (!info.date) return null;
  const link = match.links.apply ?? match.links.info;
  const description = [
    `${info.label}${info.note ? ` (${info.note})` : ""}.`,
    match.deadline.rule && match.deadline.rule !== `${info.label}.` ? match.deadline.rule : null,
    link ? `Gesuch: ${link}` : null,
    match.links.info && match.links.info !== link ? `Programmseite: ${match.links.info}` : null,
    `Quelle: ${match.provider}, Stand ${match.source_checked}.`,
    `${DISCLAIMER}.`,
  ]
    .filter(Boolean)
    .join("\n");
  return {
    uid: `${result.run_id}-${match.program_id}-${match.instrument_id}-${info.date}@fundpilot`,
    date: info.date,
    title: `Frist: ${match.instrument_name} (${match.program_name}) – ${info.label}`,
    description,
    url: link,
  };
}

/** Starts the download of a .ics file. */
export function downloadIcs(filename: string, events: CalendarEvent[]): void {
  const blob = new Blob([icsCalendar(events)], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function icsFilename(name: string): string {
  const slug = name
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 50);
  return `frist-${slug || "foerderangebot"}.ics`;
}
