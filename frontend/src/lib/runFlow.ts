/* What happens to the open program and the Rückfragen when the profile changes and the analysis runs again. Pure functions. */
import type { InstrumentMatch, InstrumentRef, ProfileField, ProjectProfile, QuestionSet, Rejected, RunResult } from "../api/contract";

const sameRef = (a: InstrumentRef, b: InstrumentRef) => a.program_id === b.program_id && a.instrument_id === b.instrument_id;

export type ProgramAfterRun =
  | { kind: "match"; match: InstrumentMatch }
  /** The pre-filter dropped it after the change. */
  | { kind: "rejected"; rejected: Rejected }
  | { kind: "missing" };

/** The same program in a new result, matched by program and instrument id. */
export function findProgram(result: RunResult, ref: InstrumentRef): ProgramAfterRun {
  const match = result.matches.find(m => sameRef(m, ref));
  if (match) return { kind: "match", match };
  const rejected = result.rejected.find(r => sameRef(r, ref));
  return rejected ? { kind: "rejected", rejected } : { kind: "missing" };
}

/** Questions not answered yet; "Weiss nicht" counts as an answer, so it is not asked twice. */
export function unansweredQuestions(questions: QuestionSet, answers: Record<string, string>): QuestionSet {
  // A subset of at most 10 questions is still at most 10; the tuple type cannot express that.
  return { ...questions, questions: questions.questions.filter(q => answers[q.id] === undefined) as QuestionSet["questions"] };
}

/** The profile with some fields replaced. */
export function withFields(profile: ProjectProfile, fields: Record<string, ProfileField>): ProjectProfile {
  return { ...profile, fields: { ...profile.fields, ...fields } };
}

/** Whether two profiles would give the backend different input. */
export function sameProfile(a: ProjectProfile | null, b: ProjectProfile | null): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

export interface FitChange {
  before: InstrumentMatch["fit"];
  after: InstrumentMatch["fit"];
}

/** Fit of the open program before and after a re-run, if it changed. */
export function fitChange(before: InstrumentMatch | null, after: ProgramAfterRun): FitChange | null {
  if (!before || after.kind !== "match" || before.fit === after.match.fit) return null;
  return { before: before.fit, after: after.match.fit };
}
