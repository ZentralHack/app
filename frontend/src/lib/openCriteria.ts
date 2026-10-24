/* Open criteria of one instrument and the profile fields that could decide them. Pure functions, no React. */
import type { CriterionResult, InstrumentMatch, ProjectProfile } from "../api/contract";

/** Answers to criterion questions live in the profile under this prefix; they are not edited as fields. */
export const RUECKFRAGE = "rueckfrage_";

export type OpenReason =
  /** At least one field the criterion needs is empty. */
  | { kind: "fehlt"; fields: string[] }
  /** The fields are filled, but they do not settle the criterion. */
  | { kind: "reicht_nicht"; reason: string }
  /** The knowledge base names no profile field for it (e.g. decided by a jury). */
  | { kind: "nicht_im_profil"; reason: string };

export interface OpenCriterion {
  criterion: CriterionResult;
  why: OpenReason;
}

const isFilled = (profile: ProjectProfile, name: string) => {
  const f = profile.fields[name];
  return f !== undefined && f.status !== "fehlt";
};

/** Fields the knowledge base names for the criterion, without answers to criterion questions. */
const neededFields = (c: CriterionResult) => c.profile_fields.filter(f => !f.startsWith(RUECKFRAGE));

/**
 * Every criterion of the instrument that is still `unbekannt`, with why it is open. The count shown on the
 * page is the length of this list, so count and list always use the same unit (criteria).
 */
export function openCriteria(match: InstrumentMatch, profile: ProjectProfile): OpenCriterion[] {
  return match.criteria
    .filter(c => c.state === "unbekannt")
    .map(criterion => {
      const fields = neededFields(criterion);
      const empty = fields.filter(f => !isFilled(profile, f));
      const why: OpenReason =
        empty.length > 0 ? { kind: "fehlt", fields: empty } : fields.length > 0 ? { kind: "reicht_nicht", reason: criterion.reason } : { kind: "nicht_im_profil", reason: criterion.reason };
      return { criterion, why };
    });
}

export interface EditorField {
  name: string;
  /** The open criteria this field could decide: the "Warum wir fragen" text. */
  criteria: CriterionResult[];
  missing: boolean;
}

/**
 * Fields to offer in the inline editor: what the knowledge base names for the open criteria, plus the
 * fields the check itself relied on. Empty fields first.
 */
export function editorFields(open: OpenCriterion[], profile: ProjectProfile): EditorField[] {
  const byName = new Map<string, EditorField>();
  for (const { criterion } of open) {
    for (const name of [...neededFields(criterion), ...criterion.evidence]) {
      if (name.startsWith(RUECKFRAGE)) continue;
      const entry = byName.get(name) ?? { name, criteria: [], missing: !isFilled(profile, name) };
      if (!entry.criteria.includes(criterion)) entry.criteria.push(criterion);
      byName.set(name, entry);
    }
  }
  return [...byName.values()].sort((a, b) => Number(b.missing) - Number(a.missing));
}

/** First sentence of a criterion text, for the short list. */
export function shortText(text: string, max = 140): string {
  const sentence = text.match(/^.+?[.!?](\s|$)/)?.[0].trim() ?? text;
  return sentence.length > max ? `${sentence.slice(0, max - 1).trimEnd()}…` : sentence;
}
