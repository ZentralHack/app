import { useState } from "react";
import type { InstrumentMatch } from "../../api/contract";
import { LEVEL_LABEL, t } from "../../text/de-CH";
import { CriteriaList } from "./CriteriaList";
import { FitBadge } from "./FitBadge";
import { Collapse, CriteriaBar, DeadlineFigure, Metric } from "./parts";
import { ArrowRight, Star } from "../ui/icons";

interface Props {
  match: InstrumentMatch;
  today: string;
  index: number;
  /** The top recommendation: yellow border and a star badge. */
  featured?: boolean;
  onOpen: () => void;
}

export function matchTitle(m: InstrumentMatch) {
  return m.instrument_name === m.program_name ? m.program_name : `${m.program_name}: ${m.instrument_name}`;
}

/** Compact result: title, provider, fit, deadline, criteria, funding rule as written in the source. Click opens the program page. */
export function ResultCard({ match, today, index, featured, onOpen }: Props) {
  const [showCriteria, setShowCriteria] = useState(false);
  const done = match.status === "fertig";
  const lever = match.fit === "passt_mit_anpassung" ? match.gaps.find(g => g.type === "anpassung" && (g.hint || g.lever)) : undefined;

  return (
    <article
      className={`group animate-rise overflow-hidden rounded-xl border bg-surface transition-[box-shadow,border-color] duration-200 hover:shadow-lift ${featured ? "border-star ring-1 ring-star" : "border-line hover:border-line-strong"}`}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <button type="button" onClick={onOpen} disabled={!done} className="grid w-full grid-cols-[minmax(0,1fr)_auto] gap-x-6 gap-y-4 px-5 pt-4 pb-4 text-left disabled:cursor-default">
        <div className="flex min-w-0 flex-col">
          {featured && (
            <span className="mb-2 inline-flex items-center gap-1 self-start rounded-full bg-star-soft px-2.5 py-0.5 text-xs font-semibold text-star-ink">
              <Star aria-hidden="true" className="size-3.5 text-star" />
              {t.results.recommended}
            </span>
          )}
          <h3 className="text-base">{matchTitle(match)}</h3>
          <span className="text-sm text-fg-2">
            {match.provider} · {LEVEL_LABEL[match.level]}
          </span>
        </div>
        <span className="flex items-center gap-3 self-start pt-0.5">
          {done && match.fit ? (
            <span className="animate-pop">
              <FitBadge fit={match.fit} />
            </span>
          ) : (
            <span className="h-5 w-28 rounded skeleton-sheen" aria-label={t.results.checking} />
          )}
          <ArrowRight aria-hidden="true" className="size-4 text-fg-muted transition-transform group-hover:translate-x-0.5 group-hover:text-primary-ink" />
        </span>

        {done ? (
          <div className="col-span-2 flex flex-wrap gap-x-10 gap-y-3">
            <Metric label={t.results.deadline}>
              <DeadlineFigure deadline={match.deadline} today={today} />
            </Metric>
            <Metric label={t.results.criteria}>
              <span className="pt-1.5">
                <CriteriaBar criteria={match.criteria} />
              </span>
            </Metric>
            {match.funding_summary && (
              <Metric label={t.results.funding} className="min-w-64 flex-1">
                <span className="line-clamp-2 pt-1 text-sm">{match.funding_summary}</span>
              </Metric>
            )}
          </div>
        ) : (
          <div className="col-span-2 flex gap-10">
            <span className="h-9 w-28 rounded skeleton-sheen" />
            <span className="h-9 w-24 rounded skeleton-sheen" />
          </div>
        )}

        {lever && (
          <p className="col-span-2 text-sm">
            <b className="font-semibold">{t.program.lever}:</b> {lever.hint ?? lever.lever}
          </p>
        )}
      </button>

      {done && (
        <div className="border-t border-line">
          <button
            type="button"
            aria-expanded={showCriteria}
            onClick={() => setShowCriteria(o => !o)}
            className="flex w-full items-center gap-2 px-5 py-2 text-sm font-semibold text-fg-2 transition-colors hover:bg-bg hover:text-fg"
          >
            <span aria-hidden="true" className={`transition-transform ${showCriteria ? "rotate-90" : ""}`}>
              ›
            </span>
            {t.results.criteriaToggle(match.criteria.filter(c => c.state !== "nicht_anwendbar").length)}
          </button>
          <Collapse open={showCriteria}>
            <div className="px-5 pt-1 pb-5">
              <CriteriaList criteria={match.criteria} />
            </div>
          </Collapse>
        </div>
      )}
    </article>
  );
}
