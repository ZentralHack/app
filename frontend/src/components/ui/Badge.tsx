import type { ReactNode } from "react";

export type Tone = "ok" | "warn" | "unknown" | "error" | "info" | "plain";

export const TONE: Record<Tone, string> = {
  ok: "text-ok bg-ok-soft",
  warn: "text-warn bg-warn-soft",
  unknown: "text-unknown bg-unknown-soft",
  error: "text-error bg-error-soft",
  info: "text-primary-ink bg-primary-soft",
  plain: "text-fg-2 bg-sunken",
};

/** Square status badge with a dot. */
export function Badge({ tone, children, dot = true }: { tone: Tone; children: ReactNode; dot?: boolean }) {
  return (
    <span className={`inline-flex h-7 items-center gap-1.5 whitespace-nowrap rounded-badge px-2.5 text-sm font-semibold ${TONE[tone]}`}>
      {dot && <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}
