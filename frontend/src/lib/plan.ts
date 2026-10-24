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
