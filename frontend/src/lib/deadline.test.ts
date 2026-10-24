import { describe, expect, it } from "vitest";
import type { Deadline } from "../api/contract";
import { deadlineInfo } from "./deadline";

const TODAY = "2026-10-24";
const d = (type: Deadline["type"], next_date: string | null, rule: string | null = null): Deadline => ({ type, next_date, rule });

describe("deadlineInfo", () => {
  it("never shows a past date: the heat pump with installation on 03.10.2026", () => {
    const info = deadlineInfo(d("vor_projektstart", "2026-10-03"), TODAY);
    expect(info.date).toBeNull();
    expect(info.problem).toBe("Projektstart liegt vor dem Gesuch: Gesuch muss vor Projektstart eingereicht werden.");
  });

  it("shows the backend's problem when the start is reached", () => {
    const rule = "Projektstart liegt vor dem Gesuch: Gesuch muss vor Installationsbeginn eingereicht werden.";
    const info = deadlineInfo(d("vor_projektstart", null, rule), TODAY);
    expect(info).toEqual({ label: "Gesuch vor Installationsbeginn einreichen", date: null, note: null, problem: rule });
  });

  it("names the event and the project start for a future start", () => {
    const info = deadlineInfo(d("vor_projektstart", "2026-12-01", "Gesuch vor Installationsbeginn einreichen."), TODAY);
    expect(info).toEqual({ label: "Gesuch vor Installationsbeginn einreichen", date: "2026-12-01", note: "vor Ihrem Projektstart (12/2026)", problem: null });
  });

  it("uses the KB wording for the event", () => {
    expect(deadlineInfo(d("vor_projektstart", "2027-03-01", "Gesuch vor Baubeginn digital einreichen."), TODAY).label).toBe("Gesuch vor Baubeginn einreichen");
    expect(deadlineInfo(d("vor_projektstart", null, null), TODAY).label).toBe("Gesuch vor Projektstart einreichen");
  });

  it("says which claim year a LIB date is", () => {
    const info = deadlineInfo(d("fester_termin_jaehrlich", "2027-01-31", "Beitragsjahr 2027, bemessen auf Ihre Kosten im Geschäftsjahr 2025."), TODAY);
    expect(info.label).toBe("Eingabefrist Gesuch Beitragsjahr 2027");
    expect(info.note).toBe("bemessen auf Ihre Kosten im Geschäftsjahr 2025");
    expect(info.date).toBe("2027-01-31");
  });

  it.each([
    [d("laufend", null, "Beantragung jederzeit im Eingabeportal."), "Gesuch jederzeit möglich"],
    [d("ausschreibung", "2026-11-04"), "Nächste Ausschreibung schliesst"],
    [d("fester_termin", "2027-03-01"), "Eingabefrist Gesuch"],
    [d("nach_abschluss", null), "Unterlagen nach Projektabschluss einreichen"],
    [d("unbekannt", null), "Frist nicht bekannt"],
  ])("%o → %s", (deadline, label) => {
    expect(deadlineInfo(deadline, TODAY).label).toBe(label);
  });

  it("a past fixed date is no deadline either", () => {
    const info = deadlineInfo(d("fester_termin", "2026-09-30"), TODAY);
    expect(info.date).toBeNull();
    expect(info.problem).toBe("Die Frist ist abgelaufen.");
  });

  it("today itself is still a deadline", () => {
    expect(deadlineInfo(d("fester_termin", TODAY), TODAY).date).toBe(TODAY);
  });
});
