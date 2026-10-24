import { useEffect, useState } from "react";
import type { RunResult } from "../api/contract";
import { Page } from "../components/layout/Page";
import { stepIndex, TracePanel } from "../components/trace/TracePanel";
import { Button } from "../components/ui/Button";
import { splitMatches } from "../lib/results";
import { progress, STEP_ORDER, type InstrumentLine, type TraceView } from "../lib/trace";
import { t } from "../text/de-CH";

interface Props {
  view: TraceView;
  result: RunResult | null;
  onRetry: (line: InstrumentLine) => void;
  onCancel: () => void;
  onNext: () => void;
}

/** Screen 4: the live trace. When the analysis finishes, the outcome is revealed once. */
export function TraceScreen({ view, result, onRetry, onCancel, onNext }: Props) {
  const finished = view.finished && result?.status === "fertig";
  const counts = result && splitMatches(result.matches);

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

      {finished && counts && (
        <section aria-label={t.trace.done} className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <RevealTile label={t.results.kpiGood} value={counts.good.length} tone="text-ok" delay={0} />
          <RevealTile label={t.results.kpiAdapt} value={counts.adapt.length} tone="text-warn" delay={350} />
          <RevealTile label={t.results.kpiChecked} value={result.matches.length + result.rejected.length} delay={700} />
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

/** Counts from 0 to `value` once, starting after `delay` ms. */
function useCountUp(value: number, delay: number, duration = 650) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setN(value);
      return;
    }
    let frame = 0;
    const start = performance.now() + delay;
    const tick = (now: number) => {
      const p = Math.min(1, Math.max(0, (now - start) / duration));
      setN(Math.round(value * (1 - Math.pow(1 - p, 3))));
      if (p < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, delay, duration]);
  return n;
}

function RevealTile({ label, value, tone = "text-fg", delay }: { label: string; value: number; tone?: string; delay: number }) {
  const n = useCountUp(value, delay);
  return (
    <div className="flex animate-pop flex-col gap-1 rounded-xl border border-line bg-surface px-5 py-4" style={{ animationDelay: `${delay}ms` }}>
      <span className="text-xs font-semibold tracking-wide text-fg-2">{label}</span>
      <span className={`text-4xl font-semibold tracking-tight tabular-nums ${tone}`}>{n}</span>
    </div>
  );
}
