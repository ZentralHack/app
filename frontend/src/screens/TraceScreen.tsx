import type { RunResult } from "../api/contract";
import { Page } from "../components/layout/Page";
import { SummaryLine } from "../components/results/SummaryLine";
import { stepIndex, TracePanel } from "../components/trace/TracePanel";
import { Button } from "../components/ui/Button";
import { progress, STEP_ORDER, type InstrumentLine, type TraceView } from "../lib/trace";
import { t } from "../text/de-CH";

interface Props {
  view: TraceView;
  result: RunResult | null;
  onRetry: (line: InstrumentLine) => void;
  onCancel: () => void;
  onNext: () => void;
}

/**
 * Screen 4: the live trace. During the checks it only shows progress; the counts appear once step
 * "bewertung" is done, from the same RunResult and with the same wording as the results page.
 */
export function TraceScreen({ view, result, onRetry, onCancel, onNext }: Props) {
  const scored = view.stages.bewertung.status === "fertig" && result !== null && result.matches.every(m => m.status === "fertig" || m.status === "fehler");

  return (
    <Page>
      <header className="flex flex-col gap-4">
        <h1>{t.trace.title}</h1>
        <div className="flex max-w-xl items-center gap-4">
          <span className="text-sm font-semibold whitespace-nowrap text-fg-2">
            {view.finished ? t.trace.done : t.trace.step(stepIndex(view), STEP_ORDER.length)}
          </span>
          <div aria-hidden="true" className="h-1 flex-1 overflow-hidden rounded-full bg-line">
            <i className="block h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${progress(view) * 100}%` }} />
          </div>
        </div>
      </header>

      <TracePanel view={view} result={result} onRetry={onRetry} />

      {scored && (
        <section aria-label={t.trace.done} className="animate-pop rounded-xl border border-line bg-surface px-5 py-4">
          <SummaryLine result={result} className="text-lg" />
        </section>
      )}

      <div className="flex justify-between gap-3">
        <Button variant="ghost" onClick={onCancel} disabled={view.finished}>
          {t.common.cancel}
        </Button>
        <Button onClick={onNext} disabled={!view.finished}>
          {t.trace.toResults} <span aria-hidden="true">→</span>
        </Button>
      </div>
    </Page>
  );
}
