/* The criteria checklist on the program page, grouped by what the user can do. Pure functions, no React. */
import type { CriterionResult, InstrumentMatch, ProjectProfile } from "../api/contract";
import { openCriteria, type OpenCriterion } from "./openCriteria";

/** Order on the page: what blocks first, what the user can still do next, what is done last. */
export const GROUP_ORDER = ["nicht_erfuellt", "offen", "erfuellbar", "gesuch", "erfuellt"] as const;
export type GroupKey = (typeof GROUP_ORDER)[number];

export interface CriteriaItem {
  criterion: CriterionResult;
  /** Set for open criteria: why it is open and what the user can enter. */
  open: OpenCriterion | null;
}

export interface CriteriaGroup {
  key: GroupKey;
  items: CriteriaItem[];
}

/**
 * ✗ → nicht erfüllt; ? with something the user can enter → offen; ? without (documents, guarantees, jury) →
 * im Gesuch nachzuweisen; ~ → erfüllbar or assumed; ✓ → erfüllt. Not applicable criteria are left out.
 */
export function criteriaGroups(match: InstrumentMatch, profile: ProjectProfile, extracted: ProjectProfile | null = null): CriteriaGroup[] {
  const open = new Map(openCriteria(match, profile, extracted).map(o => [o.criterion.criterion_id, o]));
  const groups = new Map<GroupKey, CriteriaItem[]>(GROUP_ORDER.map(k => [k, []]));
  for (const c of match.criteria) {
    const o = open.get(c.criterion_id) ?? null;
    const key: GroupKey | null =
      c.state === "nicht_erfuellt" ? "nicht_erfuellt"
      : c.state === "unbekannt" ? (o && o.inputs.length > 0 ? "offen" : "gesuch")
      : c.state === "annahme" ? "erfuellbar"
      : c.state === "erfuellt" ? "erfuellt"
      : null;
    if (key) groups.get(key)!.push({ criterion: c, open: o });
  }
  return GROUP_ORDER.map(key => ({ key, items: groups.get(key)! })).filter(g => g.items.length > 0);
}

export type GroupCounts = Record<GroupKey, number> & { total: number };

export function groupCounts(groups: CriteriaGroup[]): GroupCounts {
  const counts = Object.fromEntries(GROUP_ORDER.map(k => [k, 0])) as Record<GroupKey, number>;
  for (const g of groups) counts[g.key] = g.items.length;
  return { ...counts, total: groups.reduce((n, g) => n + g.items.length, 0) };
}

/** Anchor id of a criterion in the checklist, for links from the open-points box. */
export const criterionAnchor = (c: CriterionResult) => `kriterium-${c.criterion_id}`;
