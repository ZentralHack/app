import { describe, expect, it } from "vitest";
import { readPlace, writePlace } from "./location";

describe("place in the URL", () => {
  it("round-trips step, run and program", () => {
    const place = { step: 5, run: "run_ab12", program: { program_id: "lib", instrument_id: "lib-beitrag" } };
    expect(writePlace(place)).toBe("?schritt=5&run=run_ab12&angebot=lib%3Alib-beitrag");
    expect(readPlace(writePlace(place))).toEqual(place);
  });

  it("start page is the bare address; junk falls back to step 1", () => {
    expect(writePlace({ step: 1, run: null, program: null })).toBe("");
    expect(readPlace("")).toEqual({ step: 1, run: null, program: null });
    expect(readPlace("?schritt=9&angebot=kaputt")).toEqual({ step: 1, run: null, program: null });
  });
});

import { deadlineText } from "../components/results/parts";

it("LIB date explains the claim year, without urgency colour", () => {
  const d = deadlineText({ type: "fester_termin_jaehrlich", rule: "Beitragsjahr 2029, bemessen auf Ihre Kosten im Geschäftsjahr 2027.", next_date: "2029-01-31" }, "2026-10-24");
  expect(d).toEqual({ main: "31.01.2029", sub: "Beitragsjahr 2029, bemessen auf Ihre Kosten im Geschäftsjahr 2027", urgency: "normal" });
});
