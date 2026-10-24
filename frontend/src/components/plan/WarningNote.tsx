import type { CombinationWarning } from "../../api/contract";
import { t } from "../../text/de-CH";
import { SourceChip } from "../results/parts";
import { AlertTriangle } from "../ui/icons";

/** Inline note under the step it affects: amber icon and label, the rule in plain text, its source. */
export function WarningNote({ warning, others }: { warning: CombinationWarning; others: string[] }) {
  return (
    <div className="mt-1 grid grid-cols-[16px_minmax(0,1fr)] gap-x-2 gap-y-1.5 text-sm">
      <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 text-warn" />
      <p>
        <b className="font-semibold text-warn">{warning.type === "bedingt" ? t.program.combination : t.program.warning}</b>
        {others.length > 0 && <span className="text-fg-2"> · mit {others.join(", ")}</span>}
        <br />
        {warning.text}
      </p>
      {warning.source && (
        <span className="col-start-2">
          <SourceChip source={warning.source} />
        </span>
      )}
    </div>
  );
}
