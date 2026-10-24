import { FIT_LABEL, type Fit } from "../../text/de-CH";

const DOT: Record<Fit, string> = { passt_gut: "bg-ok", passt_mit_anpassung: "bg-warn", passt_nicht: "bg-line-strong" };
const TEXT: Record<Fit, string> = { passt_gut: "text-ok", passt_mit_anpassung: "text-warn", passt_nicht: "text-fg-2" };

/** Calm fit label: coloured dot plus text, no pill (Linear project health). */
export function FitBadge({ fit }: { fit: Fit }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap text-sm font-semibold ${TEXT[fit]}`}>
      <span aria-hidden="true" className={`size-2 rounded-full ${DOT[fit]}`} />
      {FIT_LABEL[fit]}
    </span>
  );
}
