import type { RunResult } from "../../api/contract";
import { resultGroups, summaryParts, type SummaryTone } from "../../lib/summary";
import { t } from "../../text/de-CH";

const TONE: Record<SummaryTone, string> = { ok: "text-ok", warn: "text-warn", neutral: "text-fg-2", error: "text-error" };

/** "0 passen gut  5 mit Anpassung  1 begleitendes Angebot  12 nicht passend". Used by the trace and the results page. */
export function SummaryLine({ result, className = "" }: { result: RunResult; className?: string }) {
  return (
    <p className={`flex flex-wrap gap-x-4 gap-y-1 font-semibold tabular-nums ${className}`} data-testid="summary">
      {summaryParts(resultGroups(result)).map(p => (
        <span key={p.key} className={TONE[p.tone]}>
          {t.results.summary[p.key](p.n)}
        </span>
      ))}
    </p>
  );
}
