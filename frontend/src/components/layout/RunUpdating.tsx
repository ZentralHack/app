import { progress, STEP_ORDER, type TraceView } from "../../lib/trace";
import { t } from "../../text/de-CH";
import { Spinner } from "../ui/Spinner";

/** Compact progress of a re-run in the background, instead of the full trace screen. */
export function RunUpdating({ view }: { view: TraceView }) {
  const running = STEP_ORDER.find(s => view.stages[s].status === "laeuft") ?? STEP_ORDER.find(s => view.stages[s].status === "wartet") ?? "fahrplan";
  const checked = view.instruments.filter(l => l.status !== "laeuft").length;
  const detail = running === "pruefung" && view.prefilter ? t.trace.checked(checked, view.prefilter.kept) : t.trace.stages[running];
  return (
    <div role="status" aria-live="polite" className="sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur" data-testid="run-updating">
      <div className="mx-auto flex w-full max-w-app items-center gap-3 px-6 py-2.5 text-sm lg:px-14">
        <Spinner />
        <span className="font-semibold">{t.update.running}</span>
        <span className="text-fg-2">· {detail}</span>
        <span aria-hidden="true" className="ml-auto h-1 w-32 overflow-hidden rounded-full bg-line">
          <i className="block h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${Math.max(0.08, progress(view)) * 100}%` }} />
        </span>
      </div>
    </div>
  );
}
