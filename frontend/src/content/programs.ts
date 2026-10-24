/* Display names of the programs, loaded once from GET /api/programs when the app starts. Until then, ids are shown. */
import type { ProgramSummary } from "../api/contract";

const names = new Map<string, string>();

export function setProgramNames(programs: ProgramSummary[]) {
  for (const p of programs) names.set(p.id, p.name);
}

export const programName = (id: string) => names.get(id) ?? id;
