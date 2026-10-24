import type { CombinationWarning, InstrumentMatch, RunResult, TimelineEntry } from "../api/contract";
import { Page } from "../components/layout/Page";
import { FitBadge } from "../components/results/FitBadge";
import { DeadlineFigure, Metric, SourceChip } from "../components/results/parts";
import { matchTitle } from "../components/results/ResultCard";
import { StatusSymbol } from "../components/ui/StatusSymbol";
import { WarningNote } from "../components/plan/WarningNote";
import { host, sameStep, uniqueWarnings } from "../lib/plan";
import { ArrowLeft, External, Mail, Phone } from "../components/ui/icons";
import { fieldLabel, formatDateShort } from "../lib/format";
import { visibleCriteria } from "../lib/results";
import { LEVEL_LABEL, PHASE_LABEL, t } from "../text/de-CH";

interface Props {
  match: InstrumentMatch;
  result: RunResult;
  onBack: () => void;
  onEditProfile: () => void;
}

interface Step {
  key: string;
  when: string;
  title: string;
  text: string | null;
  link: string | null;
  lever?: boolean;
  warnings: CombinationWarning[];
}

const PHASE_ORDER: Record<TimelineEntry["phase"], number> = { jetzt: 0, vor_projektstart: 1, gesuch: 2 };

/** One ordered list for levers, timeline, next steps and the deadline. Each action appears once. */
function buildSteps(match: InstrumentMatch, result: RunResult, warnings: CombinationWarning[]): Step[] {
  const steps: Step[] = match.gaps
    .filter(g => g.type === "anpassung" && (g.lever || g.hint))
    .map((g, i) => ({ key: `lever${i}`, when: "Zuerst", title: g.lever ?? g.hint!, text: g.lever ? g.hint : null, link: null, lever: true, warnings: [] }));

  (result.plan?.timeline ?? [])
    .filter(e => e.program_id === match.program_id && e.instrument_id === match.instrument_id)
    .sort((a, b) => PHASE_ORDER[a.phase] - PHASE_ORDER[b.phase])
    .forEach((e, i) =>
      steps.push({ key: `tl${i}`, when: e.date ? formatDateShort(e.date) : (e.date_rule ?? PHASE_LABEL[e.phase]), title: e.title, text: e.action, link: null, warnings: [] }),
    );

  for (const s of result.plan?.next_steps ?? []) {
    if (s.program_id !== match.program_id || (s.instrument_id && s.instrument_id !== match.instrument_id)) continue;
    const same = steps.find(x => sameStep(x.title + " " + (x.text ?? ""), s.text));
    if (same) same.link ??= s.link;
    else steps.push({ key: s.text, when: s.due ? formatDateShort(s.due) : PHASE_LABEL.jetzt, title: s.text, text: null, link: s.link, warnings: [] });
  }

  const deadline = match.deadline.next_date ? formatDateShort(match.deadline.next_date) : null;
  if (deadline && !steps.some(s => s.when === deadline))
    steps.push({ key: "deadline", when: deadline, title: t.program.submit, text: match.deadline.rule, link: match.links.apply, warnings: [] });

  // Combination notes belong to the submission, the last step.
  if (steps.length) steps[steps.length - 1].warnings = warnings;
  return steps;
}

/** Program page: hero with fit, funding rule and deadline; one timeline; criteria as a contributor list. */
export function ProgramScreen({ match, result, onBack, onEditProfile }: Props) {
  const warnings = uniqueWarnings(
    (result.plan?.warnings ?? []).filter(w => w.items.some(i => i.program_id === match.program_id && (!i.instrument_id || i.instrument_id === match.instrument_id))),
  );
  const steps = buildSteps(match, result, warnings);
  // Open criteria are listed with reasons below; here only their number and the profile fields that would decide them.
  const open = match.criteria.filter(c => c.state === "unbekannt");
  const openFields = [...new Set(open.flatMap(c => c.evidence).filter(f => !f.startsWith("rueckfrage_")).map(fieldLabel))];
  const contact = (result.plan?.contacts ?? []).find(c => host(c.url) && host(c.url) === host(match.links.info));
  const others = (w: CombinationWarning) =>
    w.items
      .filter(i => i.program_id !== match.program_id || i.instrument_id !== match.instrument_id)
      .map(i => {
        const m = result.matches.find(x => x.program_id === i.program_id && (!i.instrument_id || x.instrument_id === i.instrument_id));
        return m ? m.instrument_name : i.program_id;
      });

  return (
    <Page>
      <button type="button" onClick={onBack} className="-mb-4 inline-flex items-center gap-1.5 self-start text-sm font-semibold text-primary-ink underline decoration-primary-ink/30 underline-offset-4 hover:decoration-primary-ink">
        <ArrowLeft aria-hidden="true" className="size-4" />
        {t.program.back}
      </button>

      <header className="flex animate-rise flex-col gap-6">
        <div className="flex flex-col gap-2">
          <p className="text-fg-2">
            {match.provider} · {LEVEL_LABEL[match.level]}
          </p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <h1>{matchTitle(match)}</h1>
            {match.fit && <FitBadge fit={match.fit} />}
          </div>
          <p className="max-w-[52em]">{match.purpose}</p>
          <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm font-semibold">
            {match.links.info && (
              <a href={match.links.info} target="_blank" rel="noopener" className="inline-flex items-center gap-1">
                {t.program.programPage} <External aria-hidden="true" className="size-3.5" />
              </a>
            )}
            {match.links.apply && (
              <a href={match.links.apply} target="_blank" rel="noopener" className="inline-flex items-center gap-1">
                {t.program.apply} <External aria-hidden="true" className="size-3.5" />
              </a>
            )}
            <span title={t.program.askSoon} className="cursor-not-allowed text-fg-muted">
              {t.program.ask}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap gap-x-14 gap-y-5">
          <Metric label={t.program.deadline}>
            <DeadlineFigure deadline={match.deadline} today={result.today} size="hero" />
          </Metric>
          {match.funding_summary && (
            <Metric label={t.results.funding} className="max-w-[36em] flex-1">
              <span className="pt-1 text-lg">{match.funding_summary}</span>
            </Metric>
          )}
        </div>
      </header>

      {open.length > 0 && (
        <section className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 rounded-xl border border-line px-5 py-3">
          <p>
            <b className="font-semibold">{t.program.openCount(open.length)}</b>
            {openFields.length > 0 && <span className="text-fg-2"> · {openFields.join(", ")}</span>}
          </p>
          <button type="button" onClick={onEditProfile} className="text-sm font-semibold text-primary-ink underline decoration-primary-ink/30 underline-offset-4 hover:decoration-primary-ink">
            {t.program.completeProfile}
          </button>
        </section>
      )}

      {steps.length > 0 && (
        <section className="flex flex-col gap-4">
          <h2>{t.program.course}</h2>
          <ol className="m-0 flex list-none flex-col p-0">
            {steps.map((s, i) => (
              <li key={s.key} className="relative grid animate-rise grid-cols-[110px_20px_minmax(0,1fr)] gap-x-4 pb-6 last:pb-0" style={{ animationDelay: `${i * 70}ms` }}>
                <span className="pt-0.5 text-sm font-semibold text-fg-2 tabular-nums">{s.when}</span>
                <span className="relative flex justify-center">
                  <span className={`mt-1.5 size-3 rounded-full border-2 ${s.lever ? "border-primary bg-primary" : "border-line-strong bg-surface"}`} />
                  {i < steps.length - 1 && <span aria-hidden="true" className="absolute top-5 -bottom-6 w-px bg-line" />}
                </span>
                <div className="flex min-w-0 flex-col gap-1">
                  <b className="font-semibold">
                    {s.lever && `${t.program.lever}: `}
                    {s.title}
                  </b>
                  {s.text && <p className="text-fg-2">{s.text}</p>}
                  {s.link && (
                    <a href={s.link} target="_blank" rel="noopener" className="inline-flex items-center gap-1 self-start text-sm font-semibold">
                      {t.plan.link} <External aria-hidden="true" className="size-3.5" />
                    </a>
                  )}
                  {s.warnings.map(w => (
                    <WarningNote key={w.text} warning={w} others={others(w)} />
                  ))}
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="flex flex-col gap-2">
        <h2>{t.program.criteria}</h2>
        <ul className="m-0 flex list-none flex-col divide-y divide-line border-y border-line p-0">
          {visibleCriteria(match.criteria).map((c, i) => (
            <li key={c.criterion_id} className="grid grid-cols-[24px_minmax(0,1fr)] gap-x-3 gap-y-1 py-3 md:grid-cols-[24px_minmax(0,1fr)_auto]">
              <span className="pt-0.5">{c.state !== "nicht_anwendbar" && <StatusSymbol state={c.state} />}</span>
              <div className="flex min-w-0 flex-col">
                <span className="font-semibold">{c.text}</span>
                <span className="text-fg-2">{c.reason}</span>
              </div>
              <span className="col-start-2 md:col-start-3">
                <SourceChip source={c.source} n={i + 1} />
              </span>
            </li>
          ))}
        </ul>
      </section>

      {contact && (
        <p className="flex flex-wrap gap-x-3 gap-y-1 border-t border-line pt-4 text-sm">
          <b className="font-semibold">{t.program.contact}:</b>
          <span>{contact.name}</span>
          {contact.role && <span className="text-fg-2">{contact.role}</span>}
          {contact.email && (
            <a href={`mailto:${contact.email}`} className="inline-flex items-center gap-1">
              <Mail aria-hidden="true" className="size-3.5" />
              {contact.email}
            </a>
          )}
          {contact.phone && (
            <a href={`tel:${contact.phone.replace(/\s/g, "")}`} className="inline-flex items-center gap-1">
              <Phone aria-hidden="true" className="size-3.5" />
              {contact.phone}
            </a>
          )}
        </p>
      )}
    </Page>
  );
}
