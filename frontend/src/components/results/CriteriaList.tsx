import type { CriterionResult } from "../../api/contract";
import { visibleCriteria } from "../../lib/results";
import { StatusSymbol } from "../ui/StatusSymbol";
import { SourceChip } from "./parts";

/** Criteria, worst state first, each with its reason and a numbered source chip. */
export function CriteriaList({ criteria }: { criteria: CriterionResult[] }) {
  return (
    <ul className="m-0 flex list-none flex-col gap-4 p-0">
      {visibleCriteria(criteria).map((c, i) => (
        <li key={c.criterion_id} className="grid grid-cols-[24px_minmax(0,1fr)] gap-3">
          <span className="pt-0.5">{c.state !== "nicht_anwendbar" && <StatusSymbol state={c.state} />}</span>
          <div className="flex min-w-0 flex-col items-start gap-1">
            <span className="font-semibold">{c.text}</span>
            <span className="text-fg-2">{c.reason}</span>
            <SourceChip source={c.source} n={i + 1} />
          </div>
        </li>
      ))}
    </ul>
  );
}
