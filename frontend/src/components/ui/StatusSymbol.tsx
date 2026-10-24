import type { CriterionState } from "../../text/de-CH";
import { STATE_LABEL } from "../../text/de-CH";
import { TONE, type Tone } from "./Badge";

const SYMBOL: Record<Exclude<CriterionState, "nicht_anwendbar">, { char: string; tone: Tone }> = {
  erfuellt: { char: "✓", tone: "ok" },
  annahme: { char: "~", tone: "warn" },
  unbekannt: { char: "?", tone: "unknown" },
  nicht_erfuellt: { char: "✗", tone: "error" },
};

/** ✓ ~ ? ✗ with color and a text label for screen readers. Never color alone. */
export function StatusSymbol({ state, size = "md" }: { state: Exclude<CriterionState, "nicht_anwendbar">; size?: "md" | "sm" }) {
  const { char, tone } = SYMBOL[state];
  const box = size === "sm" ? "size-5 text-xs" : "size-6 text-sm";
  return (
    <span role="img" aria-label={STATE_LABEL[state]} className={`inline-grid flex-none place-items-center rounded-md font-bold leading-none ${box} ${TONE[tone]}`}>
      {char}
    </span>
  );
}
