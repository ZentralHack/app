import { describe, expect, it } from "vitest";
import type { RunResult } from "../api/contract";
import { criteriaGroups, GROUP_ORDER, groupCounts } from "./criteriaGroups";
import { editorEntries, openCriteria } from "./openCriteria";

const runs = Object.entries(import.meta.glob("../../../backend/demo/*.json", { eager: true, import: "default" })).map(
  ([path, data]) => [path.split("/").pop()!, data as unknown as RunResult] as const,
);

describe.each(runs)("%s: criteria checklist", (_, result) => {
  const matches = result.matches.filter(m => m.status === "fertig");

  it("puts every shown criterion in exactly one group, in the agreed order", () => {
    for (const m of matches) {
      const groups = criteriaGroups(m, result.profile);
      const ids = groups.flatMap(g => g.items.map(i => i.criterion.criterion_id));
      expect(new Set(ids).size).toBe(ids.length);
      expect(ids.length).toBe(m.criteria.filter(c => c.state !== "nicht_anwendbar").length);
      const keys = groups.map(g => g.key);
      expect(keys).toEqual(GROUP_ORDER.filter(k => keys.includes(k)));
      expect(groupCounts(groups).total).toBe(ids.length);
    }
  });

  it("counts as open only what the user can still enter; the rest is for the application", () => {
    for (const m of matches)
      for (const g of criteriaGroups(m, result.profile)) {
        if (g.key === "offen") for (const i of g.items) expect(i.open?.inputs.length, i.criterion.criterion_id).toBeGreaterThan(0);
        if (g.key === "gesuch") for (const i of g.items) expect(i.open?.inputs ?? [], i.criterion.criterion_id).toEqual([]);
      }
  });

  it("the editor never asks for a value that is already given", () => {
    for (const m of matches)
      for (const e of editorEntries(openCriteria(m, result.profile))) {
        const name = e.input.kind === "field" ? e.input.name : e.input.kind === "question" ? e.input.question.profile_field : null;
        if (name) expect(result.profile.fields[name]?.status ?? "fehlt", `${m.instrument_id}:${e.input.key}`).not.toBe("angegeben");
      }
  });
});

it("an answered criterion question is not asked again", () => {
  const [, run] = runs.find(([n]) => n === "pv-schreinerei.json")!;
  const kleiv = run.matches.find(m => m.instrument_id === "kleiv")!;
  const asked = (fields: RunResult["profile"]["fields"]) =>
    editorEntries(openCriteria(kleiv, { ...run.profile, fields })).some(e => e.input.key === "q:q_zustimmung_grundeigentuemer");
  const answer = { value: "Ja", status: "angegeben" as const, origin: "rueckfrage" as const, quote: null, note: null };
  const without = { ...run.profile.fields };
  delete without.rueckfrage_zustimmung_grundeigentuemer;
  expect(asked(without)).toBe(true);
  expect(asked({ ...without, rueckfrage_zustimmung_grundeigentuemer: answer })).toBe(false);
});
