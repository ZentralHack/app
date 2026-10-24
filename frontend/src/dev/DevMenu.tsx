/*
 * Developer menu, only built when VITE_DEV_TOOLS=true (frontend/.env.local). Jumps to any step or program page
 * with the last finished run, so one feature can be checked without clicking through the flow.
 */
import { useEffect, useState } from "react";
import { api } from "../api";
import type { InstrumentRef, RunResult } from "../api/contract";

const LAST_RUN = "fundpilot.dev.lastRun";
const STEPS = ["1 Erfassen", "2 Profil", "3 Rückfragen", "4 Prüfung", "5 Ergebnisse", "6 Fahrplan"];

function stored(): string | null {
  try {
    return localStorage.getItem(LAST_RUN);
  } catch {
    return null;
  }
}

interface Props {
  /** The run shown in the app and whether it is finished; a finished one becomes the last run. */
  runId: string | null;
  finished: boolean;
  onJump: (step: number, program: InstrumentRef | null, runId: string) => void;
}

export default function DevMenu({ runId, finished, onJump }: Props) {
  const [open, setOpen] = useState(false);
  const [last, setLast] = useState<string | null>(stored);
  const [run, setRun] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId || !finished) return;
    try {
      localStorage.setItem(LAST_RUN, runId);
    } catch {
      // private mode: the menu still works for this session
    }
    setLast(runId);
  }, [runId, finished]);

  useEffect(() => {
    if (!open || !last) return;
    setError(null);
    api.getRun(last).then(setRun, () => setError(`Lauf ${last} nicht gefunden (Backend neu gestartet ohne DEV_PERSIST_RUNS?)`));
  }, [open, last]);

  const jump = (step: number, program: InstrumentRef | null = null) => {
    if (!last) return;
    onJump(step, program, last);
    setOpen(false);
  };
  const ranked = (run?.matches ?? []).filter(m => m.rank).sort((a, b) => a.rank! - b.rank!);

  return (
    <div className="fixed right-4 bottom-4 z-50 flex flex-col items-end gap-2 text-sm" data-testid="dev-menu">
      {open && (
        <div className="flex max-h-[70vh] w-72 flex-col gap-2 overflow-auto rounded-xl border border-line bg-surface p-3 shadow-lg">
          <span className="text-xs text-fg-2">{last ? `Letzter Lauf: ${last}` : "Noch kein fertiger Lauf"}</span>
          {error && <span className="text-xs text-error">{error}</span>}
          {last && !error && (
            <>
              <div className="grid grid-cols-2 gap-1">
                {STEPS.map((label, i) => (
                  <button key={label} type="button" onClick={() => jump(i + 1)} className="rounded-md border border-line px-2 py-1 text-left hover:border-primary hover:bg-primary-soft">
                    {label}
                  </button>
                ))}
              </div>
              {ranked.length > 0 && <span className="pt-1 text-xs font-semibold text-fg-2">Detailseiten</span>}
              {ranked.map(m => (
                <button
                  key={`${m.program_id}:${m.instrument_id}`}
                  type="button"
                  onClick={() => jump(5, { program_id: m.program_id, instrument_id: m.instrument_id })}
                  className="truncate rounded-md px-2 py-1 text-left hover:bg-primary-soft"
                  title={m.instrument_name}
                >
                  {m.rank}. {m.instrument_name}
                </button>
              ))}
            </>
          )}
        </div>
      )}
      <button type="button" onClick={() => setOpen(o => !o)} className="rounded-full bg-primary px-4 py-2 font-semibold text-white shadow-lg">
        Dev
      </button>
    </div>
  );
}
