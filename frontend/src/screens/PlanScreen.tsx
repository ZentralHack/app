import { useState } from "react";
import type { RunResult } from "../api/contract";
import { Page } from "../components/layout/Page";
import { PageHeader } from "../components/layout/PageHeader";
import { ContactLine, planEvents, planItems, Timeline } from "../components/plan/Timeline";
import { CalendarPlus } from "../components/ui/icons";
import { downloadIcs } from "../lib/ics";
import { Button } from "../components/ui/Button";
import { daysUntil, formatDateShort } from "../lib/format";
import { t } from "../text/de-CH";

interface Props {
  result: RunResult | null;
  onEditProfile: () => void;
  onNewProject: () => void;
}

/** Screen 6: one timeline with every step, its deadline, link, contact and combination note. */
export function PlanScreen({ result, onEditProfile, onNewProject }: Props) {
  const [done, setDone] = useState<Set<string>>(new Set());

  if (!result?.plan) {
    return (
      <Page>
        <PageHeader title={t.plan.loading} />
      </Page>
    );
  }

  const { items, looseContacts } = planItems(result);
  const events = planEvents(items, result);
  const next = items.filter(i => i.date && i.date >= result.today).sort((a, b) => a.date!.localeCompare(b.date!))[0];
  const toggle = (key: string) =>
    setDone(prev => {
      const s = new Set(prev);
      if (s.has(key)) s.delete(key);
      else s.add(key);
      return s;
    });

  return (
    <Page>
      <header className="flex animate-rise flex-col gap-3">
        <h1>{t.plan.title}</h1>
        <p className="text-lg">
          {t.plan.summary(items.length)}
          {next && (
            <>
              {" "}
              {t.plan.nextDeadline} <b className="font-semibold tabular-nums">{formatDateShort(next.date!)}</b>, {t.results.inDays(daysUntil(next.date!, result.today))} ({next.program}).
            </>
          )}
        </p>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <p className="text-sm font-semibold text-fg-2">{t.plan.progress(done.size, items.length)}</p>
          {events.length > 0 && (
            <Button variant="secondary" size="sm" onClick={() => downloadIcs(t.calendar.allFile, events)} data-testid="calendar-all">
              <CalendarPlus aria-hidden="true" className="size-4" />
              {t.calendar.all}
            </Button>
          )}
        </div>
      </header>

      <Timeline result={result} items={items} done={done} onToggle={toggle} />

      {looseContacts.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2>{t.plan.contacts}</h2>
          <ul className="m-0 flex list-none flex-col divide-y divide-line border-y border-line p-0">
            {looseContacts.map(c => (
              <li key={c.name} className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 py-2.5">
                <span>
                  <b className="font-semibold">{c.role ?? c.name}</b>
                </span>
                <ContactLine contact={c} />
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="flex flex-wrap gap-3 print:hidden">
        <Button onClick={() => window.print()}>{t.plan.exportPdf}</Button>
        <Button variant="secondary" onClick={onEditProfile}>
          {t.plan.editProfile}
        </Button>
        <Button variant="ghost" onClick={onNewProject}>
          {t.plan.newProject}
        </Button>
      </div>
    </Page>
  );
}
