import { useEffect, useRef, useState } from "react";
import { t } from "../../text/de-CH";

interface Props {
  current: number;
  /** Highest step the user has reached; steps below it count as finished. */
  reachable: number;
  onNavigate: (step: number) => void;
}

type State = "done" | "current" | "todo";

const CIRCLE: Record<State, string> = {
  done: "border-ok bg-ok text-white",
  current: "border-primary bg-surface text-primary-ink animate-pulse-ring",
  todo: "border-line-strong bg-surface text-fg-muted",
};

/** Vertical roadmap: one circle per step, connected by a line that fills once the step is finished. */
export function Roadmap({ current, reachable, onNavigate }: Props) {
  const last = t.steps.length;
  // Steps whose check has already played; going back and forward again shows it without animation.
  const played = useRef(new Set<number>());
  useEffect(() => {
    for (let n = 1; n < reachable; n++) if (n !== current) played.current.add(n);
  }, [current, reachable]);
  return (
    <ol className="m-0 list-none p-0">
      {t.steps.map((label, i) => {
        const n = i + 1;
        const state: State = n === current ? "current" : n < reachable ? "done" : "todo";
        const clickable = n !== current && n <= reachable;
        return (
          <li key={label} className="relative pb-5 last:pb-0">
            {n < last && (
              <span aria-hidden="true" className="absolute top-10 bottom-1 left-[15px] w-0.5 overflow-hidden rounded-full bg-line">
                <span className={`block w-full bg-ok transition-[height] duration-500 ease-out ${n < reachable ? "h-full" : "h-0"}`} />
              </span>
            )}
            <button
              type="button"
              disabled={!clickable}
              onClick={() => onNavigate(n)}
              aria-current={state === "current" ? "step" : undefined}
              className="group -mx-2 flex w-[calc(100%+16px)] items-center gap-4 rounded-md px-2 py-1 text-left transition-colors enabled:hover:bg-bg disabled:cursor-default"
            >
              <StepCircle key={state} n={n} state={state} animate={!played.current.has(n)} />
              <span className={`text-base ${state === "current" ? "font-semibold text-fg" : state === "done" ? "text-fg" : "text-fg-muted"}`}>{label}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

/** `animate` is read once on mount, so a re-render during the animation does not cut it off. */
function StepCircle({ n, state, animate }: { n: number; state: State; animate: boolean }) {
  const [playCheck] = useState(animate && state === "done");
  return (
    <span
      className={`grid size-8 flex-none place-items-center rounded-full border-2 text-sm font-semibold tabular-nums transition-transform group-enabled:group-hover:scale-110 ${CIRCLE[state]} ${playCheck ? "animate-pop" : ""}`}
    >
      {state === "done" ? (
        <svg viewBox="0 0 16 16" fill="none" className="size-4">
          <path
            d="M3.5 8.5l3 3 6-7"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="16"
            className={playCheck ? "animate-draw" : ""}
          />
        </svg>
      ) : (
        n
      )}
    </span>
  );
}

/** Compact progress for narrow screens, where the sidebar roadmap is hidden. */
export function RoadmapCompact({ current }: { current: number }) {
  const total = t.steps.length;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-between text-base">
        <b className="font-semibold">{t.steps[current - 1]}</b>
        <span>{t.app.stepOf(current, total)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-line">
        <div className="h-full rounded-full bg-ok transition-[width] duration-500" style={{ width: `${((current - 1) / (total - 1)) * 100}%` }} />
      </div>
    </div>
  );
}
