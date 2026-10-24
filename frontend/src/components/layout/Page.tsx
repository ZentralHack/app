import type { ReactNode } from "react";
import { t } from "../../text/de-CH";

/** Content area of one screen, next to the sidebar. Ends with the disclaimer on every page. */
export function Page({ children }: { children: ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-app flex-1 flex-col gap-(--gap-section) px-6 pt-10 pb-6 lg:px-14 lg:pt-12">
      {children}
      <footer className="mt-auto border-t border-line pt-4 text-sm text-fg-2">{t.app.disclaimer}</footer>
    </main>
  );
}
