/* Formatting helpers. Pure functions, no React. */
import type { ProfileField } from "../api/contract";
import { FIELD_LABEL } from "../text/de-CH";

const DAY_MS = 24 * 60 * 60 * 1000;

/** "2027-01-31" -> "31. Januar 2027" */
export function formatDateLong(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("de-CH", { day: "numeric", month: "long", year: "numeric" });
}

/** "2026-10-23" -> "23.10.2026" */
export function formatDateShort(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("de-CH", { day: "2-digit", month: "2-digit", year: "numeric" });
}

/** Whole days from `today` to `date`, both ISO dates. */
export function daysUntil(date: string, today: string): number {
  return Math.round((Date.parse(date) - Date.parse(today)) / DAY_MS);
}

/** 400000 -> "400'000" (Swiss thousands separator) */
export function formatChf(n: number): string {
  return n.toLocaleString("de-CH").replace(/[’’]/g, "'");
}

/** Live input formatting: keeps digits only and groups thousands, "400000" -> "400'000". */
export function groupDigits(s: string): string {
  const digits = s.replace(/\D/g, "").replace(/^0+(?=\d)/, "");
  return digits ? formatChf(Number(digits)) : "";
}

/** Parses "400'000" or "400 000" into a number, or null. */
export function parseChf(s: string): number | null {
  const n = Number(s.replace(/['’\s]/g, ""));
  return s.trim() && Number.isFinite(n) ? n : null;
}

export function fieldLabel(name: string): string {
  return FIELD_LABEL[name] ?? name;
}

/** Display text for a profile value. Arrays are joined, booleans become Ja/Nein, numbers get separators. */
export function formatFieldValue(name: string, field: ProfileField): string {
  const v = field.value;
  if (v === null) return "–";
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "boolean") return v ? "Ja" : "Nein";
  if (typeof v === "number") {
    if (name === "budget" || name === "umsatz") return `CHF ${formatChf(v)}`;
    if (name === "laufzeit") return `${v} Monate`;
    return String(v);
  }
  return v;
}

export function formatDuration(ms: number): string {
  return `${(ms / 1000).toFixed(1)} s`;
}
