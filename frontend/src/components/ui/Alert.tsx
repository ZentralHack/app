import type { ReactNode } from "react";

type Tone = "info" | "warn" | "error";

const STYLE: Record<Tone, { box: string; symbol: string; char: string }> = {
  info: { box: "bg-primary-soft", symbol: "bg-primary text-white", char: "i" },
  warn: { box: "bg-warn-soft", symbol: "bg-warn text-white", char: "!" },
  error: { box: "bg-error-soft", symbol: "bg-error text-white", char: "✗" },
};

export function Alert({ tone, children }: { tone: Tone; children: ReactNode }) {
  const s = STYLE[tone];
  return (
    <div role={tone === "error" ? "alert" : "note"} className={`flex items-start gap-3 rounded-lg px-4 py-3 ${s.box}`}>
      <span aria-hidden="true" className={`mt-0.5 inline-grid size-5 flex-none place-items-center rounded-md text-xs font-bold ${s.symbol}`}>{s.char}</span>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
