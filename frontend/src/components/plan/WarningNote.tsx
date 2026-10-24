import type { CombinationWarning } from "../../api/contract";
import { t } from "../../text/de-CH";
import { SourceChip } from "../results/parts";

/** Small amber note attached to the step it affects, with its source. */
export function WarningNote({ warning, others }: { warning: CombinationWarning; others: string[] }) {
  return (
    <div className="mt-1 flex flex-col items-start gap-1.5 rounded-lg bg-warn-soft px-3 py-2 text-sm">
      <span>
        <b className="font-semibold text-warn">{warning.type === "bedingt" ? t.program.combination : t.program.warning}</b>
        {others.length > 0 && <span className="text-fg-2"> · mit {others.join(", ")}</span>}
        <br />
        {warning.text}
      </span>
      {warning.source && <SourceChip source={warning.source} />}
    </div>
  );
}
