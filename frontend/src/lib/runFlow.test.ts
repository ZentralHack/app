import { expect, it } from "vitest";
import type { Question, QuestionSet, RunResult } from "../api/contract";
import sensora from "../../../backend/demo/sensor-prototyp.json";
import { findProgram, fitChange, sameProfile, unansweredQuestions, withFields } from "./runFlow";

const result = sensora as unknown as RunResult;
const eic = { program_id: "eic-accelerator", instrument_id: "eic-accelerator" };

/** The result of a re-run, as the backend would send it after a profile change. */
function rerun(change: (r: RunResult) => RunResult): RunResult {
  return change(structuredClone(result));
}

it("finds the same program in the new result by instrument id", () => {
  const after = rerun(r => ({ ...r, run_id: "neu", matches: [...r.matches].reverse() }));
  const found = findProgram(after, eic);
  expect(found.kind).toBe("match");
  expect(found.kind === "match" && found.match.instrument_id).toBe("eic-accelerator");
});

it("says why a program dropped out after a change", () => {
  const after = rerun(r => {
    const m = r.matches.find(x => x.program_id === eic.program_id)!;
    return {
      ...r,
      matches: r.matches.filter(x => x !== m),
      rejected: [...r.rejected, { ...eic, program_name: m.program_name, instrument_name: m.instrument_name, reason: "Nur für KMU.", rule: "mitarbeitende", availability_status: null, next_round: null }],
    };
  });
  const found = findProgram(after, eic);
  expect(found.kind === "rejected" && found.rejected.reason).toBe("Nur für KMU.");
  expect(findProgram({ ...after, rejected: [] }, eic).kind).toBe("missing");
});

it("reports a changed fit, and nothing when it stayed", () => {
  const before = result.matches.find(m => m.program_id === eic.program_id)!;
  const better = rerun(r => ({ ...r, matches: r.matches.map(m => (m.program_id === eic.program_id ? { ...m, fit: "passt_gut" } : m)) }));
  expect(fitChange(before, findProgram(better, eic))).toEqual({ before: "passt_mit_anpassung", after: "passt_gut" });
  expect(fitChange(before, findProgram(result, eic))).toBeNull();
});

it("a field edit changes the profile the next run gets", () => {
  const edited = withFields(result.profile, { laufzeit: { value: 24, status: "angegeben", origin: "korrektur", quote: null, note: null } });
  expect(edited.fields.laufzeit.value).toBe(24);
  expect(edited.fields.vorhaben_beschreibung).toEqual(result.profile.fields.vorhaben_beschreibung);
  expect(sameProfile(edited, result.profile)).toBe(false);
  expect(sameProfile(structuredClone(result.profile), result.profile)).toBe(true);
});

it("does not ask answered Rückfragen again, also not after Weiss nicht", () => {
  const q = (id: string) => ({ id, profile_field: id, text: id, why: "", input: "auswahl", unit: null, options: ["Ja", "Weiss nicht"], affects: [], prefill: null }) as unknown as Question;
  const set = { questions: [q("partner"), q("budget"), q("laufzeit")] } as unknown as QuestionSet;
  const open = unansweredQuestions(set, { partner: "Ja", budget: "Weiss nicht" });
  expect(open.questions.map(x => x.id)).toEqual(["laufzeit"]);
});
