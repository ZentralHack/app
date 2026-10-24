import type { ReactNode } from "react";
import { progress, STEP_ORDER, type TraceView } from "../../lib/trace";
import { t } from "../../text/de-CH";
import { Spinner } from "../ui/Spinner";

/** One sticky line at the top: progress of a re-run, then its outcome in the same place, so nothing below moves. */
function Bar({ testId, children }: { testId: string; children: ReactNode }) {
  return (
    <div role="status" aria-live="polite" className="sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur" data-testid={testId}>
      <div className="mx-auto flex min-h-11 w-full max-w-app items-center gap-3 px-6 py-2.5 text-sm lg:px-14">{children}</div>
    </div>
  );
}

/** Compact progress of a re-run in the background, instead of the full trace screen. */
export function RunUpdating({ view }: { view: TraceView }) {
  const running = STEP_ORDER.find(s => view.stages[s].status === "laeuft") ?? STEP_ORDER.find(s => view.stages[s].status === "wartet") ?? "fahrplan";
  const checked = view.instruments.filter(l => l.status !== "laeuft").length;
  const detail = running === "pruefung" && view.prefilter ? t.trace.checked(checked, view.prefilter.kept) : t.trace.stages[running];
  return (
    <Bar testId="run-updating">
      <Spinner />
      <span className="font-semibold">{t.update.running}</span>
      <span className="text-fg-2">· {detail}</span>
      <span aria-hidden="true" className="ml-auto h-1 w-32 overflow-hidden rounded-full bg-line">
        <i className="block h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${Math.max(0.08, progress(view)) * 100}%` }} />
      </span>
    </Bar>
  );
}

/** What changed after the re-run, in the place the progress was. */
export function RunUpdated({ text, onClose }: { text: string; onClose: () => void }) {
  return (
    <Bar testId="notice">
      <span aria-hidden="true" className="inline-grid size-5 flex-none place-items-center rounded-md bg-primary text-xs font-bold text-white">
        i
      </span>
      <span className="font-semibold">{text}</span>
      <button type="button" onClick={onClose} className="ml-auto text-sm font-semibold text-primary-ink underline decoration-primary-ink/30 underline-offset-4 hover:decoration-primary-ink">
        {t.update.close}
      </button>
    </Bar>
  );
}
