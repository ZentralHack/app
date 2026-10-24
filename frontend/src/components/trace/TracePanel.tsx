import type { ReactNode } from "react";
import type { RunResult, SourceLink } from "../../api/contract";
import { groupRejected } from "../../lib/results";
import { STEP_ORDER, type InstrumentLine, type StageStatus, type TraceView } from "../../lib/trace";
import { REJECT_RULE_LABEL, t } from "../../text/de-CH";
import { FitBadge } from "../results/FitBadge";
import { SourceChip } from "../results/parts";
import { Button } from "../ui/Button";
import { Spinner } from "../ui/Spinner";
import { StatusSymbol } from "../ui/StatusSymbol";

interface Props {
  view: TraceView;
  result: RunResult | null;
  onRetry: (line: InstrumentLine) => void;
}

/** Live trace: steps appear as they finish, each check with its sources. */
export function TracePanel({ view, result, onRetry }: Props) {
  const sourcesOf = (l: InstrumentLine): SourceLink[] => {
    const m = result?.matches.find(x => x.program_id === l.program_id && x.instrument_id === l.instrument_id);
    const seen = new Set<string>();
    return (m?.criteria ?? []).map(c => c.source).filter(s => !seen.has(s.title) && seen.add(s.title)).slice(0, 2);
  };

  return (
    <ol role="log" aria-live="polite" className="m-0 flex list-none flex-col p-0">
      <Stage name="vorfilter" status={view.stages.vorfilter.status}>
        {view.prefilter && view.totals && (
          <Line>
            {view.totals.instruments} Instrumente in {view.totals.programs} Programmen geprüft, <b className="font-semibold">{view.prefilter.kept} kommen in Frage</b>.
          </Line>
        )}
        {view.prefilter &&
          groupRejected(view.prefilter.rejected).map(g => (
            <Line key={`${g.program_id}|${g.rule}`} muted>
              {g.program_name}
              {g.instruments.length > 1 && ` (${t.results.instruments(g.instruments.length)})`}: {REJECT_RULE_LABEL[g.rule]}
            </Line>
          ))}
      </Stage>

      <Stage name="pruefung" status={view.stages.pruefung.status}>
        {view.instruments.map(l => (
          <Line key={l.key} icon={l.status === "laeuft" ? <Spinner /> : <StatusSymbol state={l.status === "fehler" ? "nicht_erfuellt" : "erfuellt"} size="sm" />}>
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
              <span className="font-semibold">{l.name}</span>
              {l.status === "laeuft" && <span className="text-fg-2">{t.trace.running}</span>}
              {l.status === "fertig" && l.fit && <FitBadge fit={l.fit} />}
              {l.status === "fehler" && (
                <>
                  <span className="text-error">{l.error}</span>
                  {l.retryable && (
                    <Button variant="secondary" size="sm" onClick={() => onRetry(l)}>
                      {t.common.retry}
                    </Button>
                  )}
                </>
              )}
            </span>
            {l.status === "fertig" && (
              <span className="mt-1.5 flex flex-wrap gap-1.5">
                {sourcesOf(l).map((s, i) => (
                  <span key={s.title} className="animate-pop" style={{ animationDelay: `${150 + i * 80}ms` }}>
                    <SourceChip source={s} n={i + 1} />
                  </span>
                ))}
              </span>
            )}
          </Line>
        ))}
      </Stage>

      <Stage name="bewertung" status={view.stages.bewertung.status} />

      <Stage name="fahrplan" status={view.stages.fahrplan.status} last>
        {view.plan && (
          <Line>
            {view.plan.timeline_entries} Schritte im Fahrplan, {view.plan.warnings} Kombinationshinweise.
          </Line>
        )}
      </Stage>
    </ol>
  );
}

/** 1-based number of the step that is running now. */
export function stepIndex(view: TraceView) {
  return Math.min(STEP_ORDER.filter(s => view.stages[s].status === "fertig").length + 1, STEP_ORDER.length);
}

function Stage({ name, status, last, children }: { name: keyof typeof t.trace.stages; status: StageStatus; last?: boolean; children?: ReactNode }) {
  return (
    <li className="relative grid grid-cols-[24px_minmax(0,1fr)] gap-x-4 pb-7 last:pb-0">
      {!last && <span aria-hidden="true" className="absolute top-7 bottom-1 left-[11px] w-px bg-line" />}
      <span className="flex h-6 items-center justify-center">
        {status === "fertig" ? (
          <StatusSymbol state="erfuellt" />
        ) : status === "laeuft" ? (
          <Spinner label={t.trace.running} />
        ) : (
          <span aria-hidden="true" className="size-2.5 rounded-full border-2 border-line-strong" />
        )}
      </span>
      <div className="flex min-w-0 flex-col gap-2">
        <span className={`font-semibold ${status === "wartet" ? "text-fg-muted" : ""}`}>{t.trace.stages[name]}</span>
        {children}
      </div>
    </li>
  );
}

function Line({ icon, muted, children }: { icon?: ReactNode; muted?: boolean; children: ReactNode }) {
  return (
    <div className={`grid animate-rise items-start gap-3 ${icon ? "grid-cols-[20px_minmax(0,1fr)]" : "grid-cols-1"}`}>
      {icon && <span className="flex h-6 items-center">{icon}</span>}
      <div className={`min-w-0 ${muted ? "text-fg-2" : ""}`}>{children}</div>
    </div>
  );
}
