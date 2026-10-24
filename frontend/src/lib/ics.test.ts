import { describe, expect, it } from "vitest";
import type { RunResult } from "../api/contract";
import { planEvents, planItems } from "../components/plan/Timeline";
import sensora from "../../../backend/demo/sensor-prototyp.json";
import { deadlineEvent, escapeText, foldLine, icsCalendar, icsFilename, type CalendarEvent } from "./ics";

const result = sensora as unknown as RunResult;
const lib = result.matches.find(m => m.instrument_id === "lib-beitrag")!;
const NOW = new Date("2026-10-24T08:30:00Z");

const unfold = (ics: string) => ics.replace(/\r\n /g, "");
const bytes = (s: string) => new TextEncoder().encode(s).length;

describe("ics", () => {
  const event: CalendarEvent = {
    uid: "run_1-lib-lib-beitrag-2027-01-31@fundpilot",
    date: "2027-01-31",
    title: "Frist: Luzerner Innovationsbeitrag (LIB) – Eingabefrist Gesuch Beitragsjahr 2027",
    description: "Gesuch einreichen; Unterlagen: Berechnungsformular, Jahresrechnung.\nOrientierungshilfe, keine verbindliche Beurteilung.",
    url: "https://standortfoerderung.lu.ch/LIB",
  };
  const ics = icsCalendar([event], NOW);

  it("uses CRLF only and ends with a line break", () => {
    expect(ics.endsWith("\r\n")).toBe(true);
    expect(ics.replace(/\r\n/g, "")).not.toMatch(/[\r\n]/);
  });

  it("is one all-day event with two reminders", () => {
    const text = unfold(ics);
    expect(text).toMatch(/^BEGIN:VCALENDAR\r\nVERSION:2\.0\r\nPRODID:/);
    expect(text).toContain("DTSTART;VALUE=DATE:20270131\r\n");
    expect(text).toContain("DTEND;VALUE=DATE:20270201\r\n");
    expect(text).toContain("DTSTAMP:20261024T083000Z\r\n");
    expect(text.match(/BEGIN:VALARM/g)).toHaveLength(2);
    expect(text).toContain("TRIGGER:-P14D\r\n");
    expect(text).toContain("TRIGGER:-P3D\r\n");
    expect(text.match(/BEGIN:VEVENT/g)).toHaveLength(1);
    expect(text.trimEnd().endsWith("END:VCALENDAR")).toBe(true);
  });

  it("escapes commas, semicolons, backslashes and line breaks", () => {
    expect(escapeText("a,b;c\\d\ne")).toBe("a\\,b\\;c\\\\d\\ne");
    expect(unfold(ics)).toContain("DESCRIPTION:Gesuch einreichen\\; Unterlagen: Berechnungsformular\\, Jahresrechnung.\\nOrientierungshilfe\\, keine verbindliche Beurteilung.");
  });

  it("folds at 75 bytes without splitting umlauts", () => {
    for (const line of ics.split("\r\n")) expect(bytes(line)).toBeLessThanOrEqual(75);
    const long = "SUMMARY:" + "Förderprogramm Energie Kanton Luzern: Wärmepumpen ".repeat(4);
    const folded = foldLine(long);
    expect(folded.replace(/\r\n /g, "")).toBe(long);
    for (const line of folded.split("\r\n")) expect(bytes(line)).toBeLessThanOrEqual(75);
    expect(unfold(ics)).toContain("Luzerner Innovationsbeitrag (LIB) – Eingabefrist");
  });

  it("builds the LIB event from the result, with label, link, source and disclaimer", () => {
    const e = deadlineEvent(lib, result)!;
    expect(e.date).toBe("2027-01-31");
    expect(e.title).toBe(`Frist: ${lib.instrument_name} (${lib.program_name}) – Eingabefrist Gesuch`);
    expect(e.description).toContain(lib.links.apply ?? lib.links.info!);
    expect(e.description).toContain(`Quelle: ${lib.provider}`);
    expect(e.description).toContain("Orientierungshilfe, keine verbindliche Beurteilung.");
  });

  it("no event without a real future date", () => {
    const past = { ...lib, deadline: { ...lib.deadline, next_date: "2026-10-03" } };
    expect(deadlineEvent(past, result)).toBeNull();
    const none = { ...lib, deadline: { type: "laufend" as const, rule: null, next_date: null } };
    expect(deadlineEvent(none, result)).toBeNull();
  });

  it("file names are plain", () => {
    expect(icsFilename("Wärmepumpen (Luft/Wasser)")).toBe("frist-warmepumpen-luft-wasser.ics");
  });
});

describe("Fahrplan calendar", () => {
  const runs = Object.values(import.meta.glob("../../../backend/demo/*.json", { eager: true, import: "default" })) as unknown as RunResult[];

  it.each(runs.map(r => [r.run_id, r] as const))("%s: one valid event per dated future step, never a past date", (_, run) => {
    if (!run.plan) return;
    const events = planEvents(planItems(run).items, run);
    expect(new Set(events.map(e => e.uid)).size).toBe(events.length);
    for (const e of events) expect(e.date >= run.today).toBe(true);
    const ics = icsCalendar(events, NOW);
    expect(ics.match(/BEGIN:VEVENT/g)?.length ?? 0).toBe(events.length);
    for (const line of ics.split("\r\n")) expect(bytes(line)).toBeLessThanOrEqual(75);
  });

  it("drops a step whose date is in the past", () => {
    const run = structuredClone(result);
    run.plan!.timeline = run.plan!.timeline.map(e => ({ ...e, date: "2026-10-03" }));
    const { items } = planItems(run);
    expect(items.every(i => i.date === null || i.date >= run.today)).toBe(true);
    expect(planEvents(items, run).every(e => e.date >= run.today)).toBe(true);
  });
});
