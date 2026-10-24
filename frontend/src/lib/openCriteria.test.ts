import { describe, expect, it } from "vitest";
import type { InstrumentMatch, ProfileField, RunResult } from "../api/contract";
import pv from "../../../backend/demo/pv-schreinerei.json";
import sensora from "../../../backend/demo/sensor-prototyp.json";
import { conflictOf, editorEntries, openCriteria, RUECKFRAGE, shortText } from "./openCriteria";

const runs = Object.entries(import.meta.glob("../../../backend/demo/*.json", { eager: true, import: "default" })).map(
  ([path, data]) => [path.split("/").pop()!, data as unknown as RunResult] as const,
);
const FREE_TEXT = ["vorhaben_beschreibung", "taetigkeit"];

describe.each(runs)("%s: every open criterion", (_, result) => {
  const matches = result.matches.filter(m => m.status === "fertig");

  it("either has inputs that can change it, or no button", () => {
    for (const m of matches) {
      for (const o of openCriteria(m, result.profile)) {
        const where = `${m.instrument_id}:${o.criterion.criterion_id}`;
        for (const input of o.inputs) {
          if (input.kind === "field") expect(["fehlt", "annahme"], where).toContain(result.profile.fields[input.name]?.status ?? "fehlt");
          if (input.kind === "text") expect(FREE_TEXT, where).toContain(input.name);
          if (input.kind === "question") {
            expect(input.question.affects.some(a => a.criterion_id === o.criterion.criterion_id), where).toBe(true);
            expect(input.question.options.some(x => x !== "Weiss nicht") || input.question.input !== "auswahl", where).toBe(true);
            expect(input.question.prefill, where).toBeNull();
          }
        }
        if (o.inputs.length === 0) expect(["gesuch", "reicht_nicht"], where).toContain(o.why.kind);
        if (o.criterion.kind === "bewertung") expect(o.inputs, where).toEqual([]);
        if (o.why.kind === "fehlt") for (const f of o.why.fields) expect(result.profile.fields[f]?.status ?? "fehlt", where).toBe("fehlt");
      }
    }
  });

  it("never offers a filled yes/no, choice or number field again", () => {
    for (const m of matches)
      for (const e of editorEntries(openCriteria(m, result.profile)))
        if (e.input.kind === "field") expect(result.profile.fields[e.input.name]?.status ?? "fehlt").not.toBe("angegeben");
  });

  it("the button shows exactly when there is an input", () => {
    for (const m of matches) {
      const open = openCriteria(m, result.profile);
      expect(editorEntries(open).length > 0).toBe(open.some(o => o.inputs.length > 0));
    }
  });
});

const sensoraRun = sensora as unknown as RunResult;
const eic = sensoraRun.matches.find(m => m.program_id === "eic-accelerator") as InstrumentMatch;

it("EIC: count equals list, the jury criterion is left to the application", () => {
  const open = openCriteria(eic, sensoraRun.profile);
  expect(open.length).toBe(eic.criteria.filter(c => c.state === "unbekannt").length);
  const jury = open.find(o => o.criterion.criterion_id === "auswahl_jury")!;
  expect(jury.why.kind).toBe("gesuch");
  expect(jury.inputs).toEqual([]);
  // TRL: its own question first, then the description (filled, but silent on TRL); Laufzeit is filled and not offered.
  const trl = open.find(o => o.criterion.criterion_id === "trl_6_8")!;
  expect(trl.inputs.map(i => i.key)).toEqual(["q:q_trl_6_8", "t:vorhaben_beschreibung"]);
});

describe("Gebäudeeigentum (PV)", () => {
  const run = pv as unknown as RunResult;
  const kleiv = run.matches.find(m => m.instrument_id === "kleiv") as InstrumentMatch;
  const corrected: ProfileField = { value: false, status: "angegeben", origin: "korrektur", quote: null, note: null };
  const profile = { ...run.profile, fields: { ...run.profile.fields, eigentum_gebaeude: corrected } };

  it("offers the criterion's own question instead of the filled yes/no field", () => {
    const o = openCriteria(kleiv, run.profile).find(x => x.criterion.criterion_id === "zustimmung_grundeigentuemer")!;
    expect(o.inputs.map(i => i.key)).toEqual(["q:q_zustimmung_grundeigentuemer"]);
    const q = o.inputs[0];
    expect(q.kind === "question" && q.question.profile_field).toBe(`${RUECKFRAGE}zustimmung_grundeigentuemer`);
  });

  it("shows a correction against the description as a contradiction with both values", () => {
    expect(conflictOf("eigentum_gebaeude", profile, run.profile)).toMatchObject({ fromText: { value: true }, current: { value: false } });
    const o = openCriteria(kleiv, profile, run.profile).find(x => x.criterion.criterion_id === "zustimmung_grundeigentuemer")!;
    expect(o.why.kind).toBe("widerspruch");
    expect(o.inputs.map(i => i.kind)).toEqual(["conflict", "question"]);
  });

  it("no contradiction without a correction, or when the correction agrees", () => {
    expect(conflictOf("eigentum_gebaeude", run.profile, run.profile)).toBeNull();
    const same = { ...profile, fields: { ...profile.fields, eigentum_gebaeude: { ...corrected, value: true } } };
    expect(conflictOf("eigentum_gebaeude", same, run.profile)).toBeNull();
  });
});

it("short text does not stop at abbreviations", () => {
  expect(shortText("Nachweis über nachhaltiges Wirtschaften: Bericht nach Art. 964b OR (auch auf Gruppenstufe). Weiteres.")).toBe(
    "Nachweis über nachhaltiges Wirtschaften: Bericht nach Art. 964b OR (auch auf Gruppenstufe).",
  );
  expect(shortText("Gilt z. B. für Hotels. Mehr.")).toBe("Gilt z. B. für Hotels.");
  expect(shortText("Das Gesuch ist vor Installationsbeginn eingereicht.")).toBe("Das Gesuch ist vor Installationsbeginn eingereicht.");
});
