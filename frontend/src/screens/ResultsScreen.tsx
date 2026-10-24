import { Tabs } from "@heroui/react";
import { useState } from "react";
import type { InstrumentMatch, InstrumentRef, RunResult } from "../api/contract";
import { Page } from "../components/layout/Page";
import { PageHeader } from "../components/layout/PageHeader";
import { RejectedList } from "../components/results/RejectedList";
import { matchTitle, ResultCard } from "../components/results/ResultCard";
import { FitBadge } from "../components/results/FitBadge";
import { ArrowRight } from "../components/ui/icons";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { isAdvisory, splitMatches } from "../lib/results";
import { t } from "../text/de-CH";

interface Props {
  result: RunResult | null;
  company: string | null;
  onOpen: (ref: InstrumentRef) => void;
  onRetry: (match: InstrumentMatch) => void;
  onNext: () => void;
}

/** Screen 5: compact cards, the top recommendation first and marked. A card opens its program page. */
export function ResultsScreen({ result, company, onOpen, onRetry, onNext }: Props) {
  const [tab, setTab] = useState("passende");

  if (!result) {
    return (
      <Page>
        <PageHeader title={t.results.loading} />
      </Page>
    );
  }

  const running = result.status === "laeuft";
  const split = splitMatches(result.matches);
  const { notFit, failed } = split;
  // Money first; advice and coaching get their own quiet section below.
  const good = split.good.filter(m => !isAdvisory(m));
  const adapt = split.adapt.filter(m => !isAdvisory(m));
  const advice = [...split.good, ...split.adapt].filter(isAdvisory);
  const fitting = [...good, ...adapt];
  const pending = result.matches.filter(m => m.status === "ausstehend" || m.status === "laeuft");
  const top = fitting[0];
  const open = (m: InstrumentMatch) => onOpen({ program_id: m.program_id, instrument_id: m.instrument_id });
  const cards = (list: InstrumentMatch[]) =>
    list.map((m, i) => <ResultCard key={`${m.program_id}:${m.instrument_id}`} match={m} today={result.today} index={i} featured={m === top} onOpen={() => open(m)} />);

  return (
    <Page>
      <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <PageHeader title={running && fitting.length === 0 ? t.results.loading : t.results.heading(company)} lead={running || top ? undefined : t.results.nothing}>
          {!running && top && (
            <p className="flex flex-wrap gap-x-4 text-lg font-semibold">
              <span className="text-ok">{t.results.counts(good.length, adapt.length).good}</span>
              <span className="text-warn">{t.results.counts(good.length, adapt.length).adapt}</span>
            </p>
          )}
        </PageHeader>
        <Button onClick={onNext} disabled={!result.plan}>
          {t.results.toPlan} <ArrowRight aria-hidden="true" className="size-4" />
        </Button>
      </header>

      {failed.map(m => (
        <Alert key={m.instrument_id} tone="error">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>{t.results.failed(m.instrument_name)}</span>
            <Button variant="secondary" size="sm" onClick={() => onRetry(m)}>
              {t.common.retry}
            </Button>
          </div>
        </Alert>
      ))}

      <Tabs selectedKey={tab} onSelectionChange={k => setTab(String(k))} variant="secondary">
        <Tabs.ListContainer>
          <Tabs.List aria-label="Ansicht">
            <Tabs.Tab id="passende">
              {t.results.tabFitting} ({fitting.length + advice.length})
              <Tabs.Indicator />
            </Tabs.Tab>
            <Tabs.Tab id="alle">
              {t.results.tabAll} ({result.matches.length + result.rejected.length})
              <Tabs.Indicator />
            </Tabs.Tab>
          </Tabs.List>
        </Tabs.ListContainer>
        <Tabs.Panel id="passende" className="flex flex-col gap-10 pt-5">
          <div className="flex flex-col gap-3">{cards([...fitting, ...pending])}</div>
          {advice.length > 0 && <AdviceList matches={advice} onOpen={open} />}
        </Tabs.Panel>
        <Tabs.Panel id="alle" className="pt-5">
          <div className="flex flex-col gap-8">
            <div className="flex flex-col gap-3">{cards([...fitting, ...pending])}</div>
            {advice.length > 0 && <AdviceList matches={advice} onOpen={open} />}
            <RejectedList notFit={notFit} rejected={result.rejected} />
          </div>
        </Tabs.Panel>
      </Tabs>
    </Page>
  );
}

/** Advice and coaching: one quiet row each, no card. */
function AdviceList({ matches, onOpen }: { matches: InstrumentMatch[]; onOpen: (m: InstrumentMatch) => void }) {
  return (
    <section aria-labelledby="advice-title" className="flex flex-col gap-2">
      <h2 id="advice-title" className="text-lg">
        {t.results.advisory}
      </h2>
      <p className="text-sm text-fg-2">{t.results.advisoryLead}</p>
      <ul className="m-0 flex list-none flex-col divide-y divide-line border-y border-line p-0">
        {matches.map(m => (
          <li key={`${m.program_id}:${m.instrument_id}`}>
            <button type="button" onClick={() => onOpen(m)} className="group grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-6 gap-y-1 py-3 text-left">
              <span className="flex min-w-0 flex-col">
                <span className="font-semibold">{matchTitle(m)}</span>
                <span className="text-sm text-fg-2">{m.funding_summary}</span>
              </span>
              <span className="flex items-center gap-3">
                {m.fit && <FitBadge fit={m.fit} />}
                <ArrowRight aria-hidden="true" className="size-4 text-fg-muted group-hover:text-primary-ink" />
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
