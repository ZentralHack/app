/* The visible screen in the URL, so browser back moves between screens and a reload finds the run again. */
import type { InstrumentRef } from "../api/contract";

export interface Place {
  step: number;
  run: string | null;
  program: InstrumentRef | null;
}

/** `?schritt=5&run=run_ab12&angebot=lib:lib-beitrag`; step 1 without a run is the bare address. */
export function writePlace({ step, run, program }: Place): string {
  const params = new URLSearchParams();
  if (step > 1 || run) params.set("schritt", String(step));
  if (run) params.set("run", run);
  if (program) params.set("angebot", `${program.program_id}:${program.instrument_id}`);
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function readPlace(search: string): Place {
  const params = new URLSearchParams(search);
  const step = Number(params.get("schritt"));
  const [program_id, instrument_id] = (params.get("angebot") ?? "").split(":");
  return {
    step: Number.isInteger(step) && step >= 1 && step <= 6 ? step : 1,
    run: params.get("run") || null,
    program: program_id && instrument_id ? { program_id, instrument_id } : null,
  };
}
