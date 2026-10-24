/* Open criteria of one instrument and what the user can do about each. Pure functions, no React. */
import type { CriterionResult, InstrumentMatch, ProfileField, ProjectProfile, Question } from "../api/contract";

/** Answers to criterion questions live in the profile under this prefix; they are not edited as fields. */
export const RUECKFRAGE = "rueckfrage_";

/** Free-text fields: filling them in further can add what a criterion is missing. */
const FREE_TEXT = new Set(["vorhaben_beschreibung", "taetigkeit"]);

export interface Conflict {
  field: string;
  /** The value the profile step read from the description, with its quote. */
  fromText: ProfileField;
  /** The value the user set later. */
  current: ProfileField;
}

export type OpenReason =
  /** At least one field the criterion needs is empty. */
  | { kind: "fehlt"; fields: string[] }
  /** The user changed a field so that it no longer says what the description says. */
  | { kind: "widerspruch"; conflicts: Conflict[] }
  /** The fields are filled, but they do not settle the criterion. */
  | { kind: "reicht_nicht"; reason: string }
  /** Decided in the application or by a jury, or nothing in a profile can decide it. */
  | { kind: "gesuch"; reason: string };

/** One thing the editor can offer. Each one can change the criterion it belongs to. */
export type EditInput =
  | { kind: "field"; key: string; name: string }
  | { kind: "text"; key: string; name: string }
  | { kind: "question"; key: string; question: Question }
  | { kind: "conflict"; key: string; conflict: Conflict };

export interface OpenCriterion {
  criterion: CriterionResult;
  why: OpenReason;
  inputs: EditInput[];
}

const fieldOf = (profile: ProjectProfile, name: string) => profile.fields[name];
const isEmpty = (f: ProfileField | undefined) => f === undefined || f.status === "fehlt";

/** Fields the knowledge base names for the criterion, without answers to criterion questions. */
const neededFields = (c: CriterionResult) => c.profile_fields.filter(f => !f.startsWith(RUECKFRAGE));

/** A field the user changed away from what the description said. */
export function conflictOf(name: string, profile: ProjectProfile, extracted: ProjectProfile | null): Conflict | null {
  const current = fieldOf(profile, name);
  const fromText = extracted ? fieldOf(extracted, name) : undefined;
  if (!current || !fromText || current.origin !== "korrektur" || current.status === "fehlt") return null;
  if (fromText.status !== "angegeben" || !fromText.quote) return null;
  return JSON.stringify(fromText.value) === JSON.stringify(current.value) ? null : { field: name, fromText, current };
}

/**
 * Every criterion of the instrument that is still `unbekannt`, with why it is open and the inputs that could
 * change it. The count on the page is the length of this list (criteria, not fields).
 *
 * Rules: a missing or assumed field → that field; a field that contradicts the description → both values to
 * choose from; the criterion's own question (or the catalog question deciding it) → answered like a Rückfrage;
 * a filled free-text field → can be extended. Jury decisions and criteria nothing in a profile can decide get
 * no input. A filled closed field (yes/no, choice, number) is never offered again: changing it adds nothing.
 */
export function openCriteria(match: InstrumentMatch, profile: ProjectProfile, extracted: ProjectProfile | null = null): OpenCriterion[] {
  return match.criteria
    .filter(c => c.state === "unbekannt")
    .map(criterion => {
      const fields = neededFields(criterion);
      const answered = criterion.question && profile.fields[criterion.question.profile_field];
      const question = answered && answered.status === "angegeben" && answered.value !== "Weiss nicht" ? null : criterion.question;
      if (criterion.kind === "bewertung" || (fields.length === 0 && !question)) {
        return { criterion, why: { kind: "gesuch", reason: criterion.reason }, inputs: [] };
      }
      const empty = fields.filter(f => isEmpty(fieldOf(profile, f)));
      const assumed = fields.filter(f => fieldOf(profile, f)?.status === "annahme");
      const conflicts = fields.map(f => conflictOf(f, profile, extracted)).filter((c): c is Conflict => c !== null);
      const inputs: EditInput[] = [];
      // A catalog question for an empty field asks better than the bare field; it writes the same field.
      const asked = question && !question.profile_field.startsWith(RUECKFRAGE) ? question.profile_field : null;
      for (const name of [...empty, ...assumed]) if (name !== asked) inputs.push({ kind: "field", key: `f:${name}`, name });
      for (const c of conflicts) inputs.push({ kind: "conflict", key: `c:${c.field}`, conflict: c });
      if (question) inputs.push({ kind: "question", key: `q:${question.id}`, question });
      for (const name of fields) if (FREE_TEXT.has(name) && !isEmpty(fieldOf(profile, name)) && !conflicts.some(c => c.field === name)) inputs.push({ kind: "text", key: `t:${name}`, name });
      const why: OpenReason =
        empty.length > 0 ? { kind: "fehlt", fields: empty } : conflicts.length > 0 ? { kind: "widerspruch", conflicts } : { kind: "reicht_nicht", reason: criterion.reason };
      return { criterion, why, inputs };
    });
}

export interface EditorEntry {
  input: EditInput;
  /** The open criteria this input can change: the "Warum wir fragen" text. */
  criteria: CriterionResult[];
}

/** The inputs of all open criteria, each once, with the criteria it serves. Conflicts and empty fields first. */
export function editorEntries(open: OpenCriterion[]): EditorEntry[] {
  const order: Record<EditInput["kind"], number> = { conflict: 0, field: 1, question: 2, text: 3 };
  const byKey = new Map<string, EditorEntry>();
  for (const o of open)
    for (const input of o.inputs) {
      const entry = byKey.get(input.key) ?? { input, criteria: [] };
      if (!entry.criteria.includes(o.criterion)) entry.criteria.push(o.criterion);
      byKey.set(input.key, entry);
    }
  return [...byKey.values()].sort((a, b) => order[a.input.kind] - order[b.input.kind]);
}

/** Words that end in a dot without ending the sentence ("Art. 964b OR", "z. B."). */
const ABBREVIATION = /(?:^|[\s(])(?:Art|Abs|Nr|Ziff|lit|bzw|ca|inkl|exkl|evtl|gem|resp|max|min|vgl|z|B|d|h|u|a|\d+)\.$/;

/** First sentence of a criterion text, for the short list; abbreviations do not end it. */
export function shortText(text: string, max = 140): string {
  let sentence = text;
  for (const m of text.matchAll(/[.!?](?=\s|$)/g)) {
    const head = text.slice(0, m.index! + 1);
    if (!ABBREVIATION.test(head)) {
      sentence = head;
      break;
    }
  }
  sentence = sentence.trim();
  return sentence.length > max ? `${sentence.slice(0, max - 1).trimEnd()}…` : sentence;
}
