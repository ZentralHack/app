import { Tabs } from "@heroui/react";
import { useState } from "react";
import type { InstrumentMatch, InstrumentRef, RunResult } from "../api/contract";
import { Page } from "../components/layout/Page";
import { PageHeader } from "../components/layout/PageHeader";
import { RejectedList } from "../components/results/RejectedList";
import { ResultCard } from "../components/results/ResultCard";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { splitMatches } from "../lib/results";
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
  const { good, adapt, notFit, failed } = splitMatches(result.matches);
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
          {t.results.toPlan} <span aria-hidden="true">→</span>
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
              {t.results.tabFitting} ({fitting.length})
              <Tabs.Indicator />
            </Tabs.Tab>
            <Tabs.Tab id="alle">
              {t.results.tabAll} ({result.matches.length + result.rejected.length})
              <Tabs.Indicator />
            </Tabs.Tab>
          </Tabs.List>
        </Tabs.ListContainer>
        <Tabs.Panel id="passende" className="pt-5">
          <div className="flex flex-col gap-3">{cards([...fitting, ...pending])}</div>
        </Tabs.Panel>
        <Tabs.Panel id="alle" className="pt-5">
          <div className="flex flex-col gap-8">
            <div className="flex flex-col gap-3">{cards([...fitting, ...pending])}</div>
            <RejectedList notFit={notFit} rejected={result.rejected} />
          </div>
        </Tabs.Panel>
      </Tabs>
    </Page>
  );
}
