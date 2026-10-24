import type { InstrumentMatch, Rejected } from "../../api/contract";
import { formatDateLong } from "../../lib/format";
import { groupRejected } from "../../lib/results";
import { t } from "../../text/de-CH";
import { matchTitle } from "./ResultCard";

interface Props {
  notFit: InstrumentMatch[];
  rejected: Rejected[];
}

/** Everything that does not fit, one line each: name and reason. Checked matches first, then pre-filter rejects. */
export function RejectedList({ notFit, rejected }: Props) {
  const rows = [
    ...notFit.map(m => ({ key: `${m.program_id}:${m.instrument_id}`, name: matchTitle(m), reason: m.criteria.find(c => c.state === "nicht_erfuellt")?.reason ?? "" })),
    ...groupRejected(rejected).map(g => ({
      key: `${g.program_id}|${g.rule}|${g.reason}`,
      name: g.instruments.length > 1 ? `${g.program_name} (${t.results.instruments(g.instruments.length)})` : g.program_name,
      reason:
        g.rule === "verfuegbarkeit" && g.instruments[0].next_round
          ? `${t.results.roundClosed}.${t.results.nextRound(formatDateLong(g.instruments[0].next_round))}`
          : g.reason,
    })),
  ];
  if (!rows.length) return null;
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-base">{t.results.notFitTitle}</h2>
      <ul className="m-0 flex list-none flex-col divide-y divide-line border-y border-line p-0">
        {rows.map(r => (
          <li key={r.key} className="grid grid-cols-1 gap-x-6 py-2.5 sm:grid-cols-[minmax(0,280px)_minmax(0,1fr)]">
            <span className="font-semibold">{r.name}</span>
            <span className="text-fg-2">{r.reason}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
