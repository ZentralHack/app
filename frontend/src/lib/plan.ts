/* Helpers for merging plan data into one list per page. Pure functions, no React. */

/** Words that identify an action; two shared words mean two texts describe the same step. */
const words = (s: string) => new Set(s.toLowerCase().split(/[^a-zäöüéè]+/).filter(w => w.length >= 5));

export const sameStep = (a: string, b: string) => [...words(a)].filter(w => words(b).has(w)).length >= 2;

/** "https://www.itz.ch/x" -> "itz.ch", used to match contacts to programs. */
export function host(url: string | null): string | null {
  try {
    return url ? new URL(url).host.replace(/^www\./, "") : null;
  } catch {
    return null;
  }
}

interface Warning {
  type: string;
  text: string;
  items: { program_id: string; instrument_id?: string | null }[];
}

/**
 * Drops warnings that say the same thing twice: the same type between the same instruments
 * (two programs often state the same deduction, each from its own side). The first one stays.
 */
export function uniqueWarnings<W extends Warning>(warnings: W[]): W[] {
  const seen = new Set<string>();
  return warnings.filter(w => {
    const key = `${w.type}|${w.items.map(i => `${i.program_id}:${i.instrument_id ?? ""}`).sort().join(",")}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
