import { expect, it } from "vitest";
import type { InstrumentMatch, RunResult } from "../api/contract";
import sensora from "../../../backend/demo/sensor-prototyp.json";
import { editorFields, openCriteria } from "./openCriteria";

const result = sensora as unknown as RunResult;
const eic = result.matches.find(m => m.program_id === "eic-accelerator") as InstrumentMatch;

it("lists the open criteria themselves, so count and list agree", () => {
  const open = openCriteria(eic, result.profile);
  expect(open.map(o => o.criterion.criterion_id)).toEqual(["trl_6_8", "ein_antrag", "auswahl_jury"]);
  expect(open.length).toBe(eic.criteria.filter(c => c.state === "unbekannt").length);
});

it("never names a filled field as missing", () => {
  const open = openCriteria(eic, result.profile);
  const trl = open.find(o => o.criterion.criterion_id === "trl_6_8")!;
  // vorhaben_beschreibung and laufzeit are filled; the description just does not state the TRL.
  expect(result.profile.fields.vorhaben_beschreibung.status).not.toBe("fehlt");
  expect(trl.why.kind).toBe("reicht_nicht");
  expect(open.find(o => o.criterion.criterion_id === "ein_antrag")!.why.kind).toBe("nicht_im_profil");
  for (const o of open) if (o.why.kind === "fehlt") for (const f of o.why.fields) expect(result.profile.fields[f]?.status ?? "fehlt").toBe("fehlt");
});

it("names the empty field when one is missing", () => {
  const profile = { ...result.profile, fields: { ...result.profile.fields, vorhaben_beschreibung: { value: null, status: "fehlt" as const, origin: null, quote: null, note: null } } };
  const trl = openCriteria(eic, profile).find(o => o.criterion.criterion_id === "trl_6_8")!;
  expect(trl.why).toEqual({ kind: "fehlt", fields: ["vorhaben_beschreibung"] });
});

it("offers the fields the open criteria need, plus what the check relied on", () => {
  const fields = editorFields(openCriteria(eic, result.profile), result.profile).map(f => f.name);
  expect(fields).toEqual(["vorhaben_beschreibung", "laufzeit"]);
});
