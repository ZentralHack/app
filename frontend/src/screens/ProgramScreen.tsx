import { useState } from "react";
import type { CombinationWarning, InstrumentMatch, ProfileField, ProjectProfile, RunResult, TimelineEntry } from "../api/contract";
import { Page } from "../components/layout/Page";
import { FitBadge } from "../components/results/FitBadge";
import { DeadlineFigure, Metric, SourceChip } from "../components/results/parts";
import { matchTitle } from "../components/results/ResultCard";
import { StatusSymbol } from "../components/ui/StatusSymbol";
import { WarningNote } from "../components/plan/WarningNote";
import { ChatDrawer } from "../components/program/ChatDrawer";
import { ProfileEditor, type EditorAnswer } from "../components/program/ProfileEditor";
import { host, sameStep, uniqueWarnings } from "../lib/plan";
import { ArrowLeft, External, Mail, Phone } from "../components/ui/icons";
import { fieldLabel, formatDateShort } from "../lib/format";
import { criteriaGroups, criterionAnchor, groupCounts, type CriteriaItem } from "../lib/criteriaGroups";
import { editorEntries, openCriteria, shortText, type OpenCriterion } from "../lib/openCriteria";
import { LEVEL_LABEL, PHASE_LABEL, t } from "../text/de-CH";

interface Props {
  match: InstrumentMatch;
  result: RunResult;
  onBack: () => void;
  onEditProfile: () => void;
  /** The profile as read from the description, to show contradictions with later corrections. */
  extracted: ProjectProfile | null;
  /** Saves fields and answers from the inline editor; the analysis runs again in the background. */
  onSaveEdits: (fields: Record<string, ProfileField>, answers: EditorAnswer[]) => void;
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
export function ProgramScreen({ match, result, extracted, onBack, onEditProfile, onSaveEdits }: Props) {
  const [editing, setEditing] = useState(false);
  const [chatting, setChatting] = useState(false);
  const warnings = uniqueWarnings(
    (result.plan?.warnings ?? []).filter(w => w.items.some(i => i.program_id === match.program_id && (!i.instrument_id || i.instrument_id === match.instrument_id))),
  );
  const steps = buildSteps(match, result, warnings);
  // Judged against the profile of this run, so "Angabe fehlt" never names a field the user filled in.
  const open = openCriteria(match, result.profile, extracted);
  // The button only appears when at least one input can change an open criterion.
  const entries = editorEntries(open);
  const groups = criteriaGroups(match, result.profile, extracted);
  const counts = groupCounts(groups);
  const actionable = groups.find(g => g.key === "offen")?.items ?? [];
  // Numbered in the order shown, so the chip numbers read top to bottom.
  const numbered = groups.flatMap(g => g.items.map(i => i.criterion.criterion_id));
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
            <button type="button" onClick={() => setChatting(true)} className="inline-flex items-center gap-1 font-semibold text-primary-ink" data-testid="ask">
              {t.program.ask}
            </button>
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

      {actionable.length > 0 && (
        <section className="flex flex-col gap-3 rounded-xl border border-line px-5 py-4" data-testid="open-criteria">
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
            <b className="font-semibold">{t.program.openCount(actionable.length)}</b>
            {entries.length > 0 && (
              <button type="button" onClick={() => setEditing(true)} className="text-sm font-semibold text-primary-ink underline decoration-primary-ink/30 underline-offset-4 hover:decoration-primary-ink">
                {t.program.completeProfile}
              </button>
            )}
          </div>
          <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
            {actionable.map(({ criterion }) => (
              <li key={criterion.criterion_id}>
                <a href={`#${criterionAnchor(criterion)}`} title={criterion.text} className="text-fg">
                  {shortText(criterion.text)}
                </a>
              </li>
            ))}
          </ul>
          {counts.gesuch > 0 && <p className="text-sm text-fg-2">{t.program.laterCount(counts.gesuch)}</p>}
        </section>
      )}

      <ProfileEditor
        isOpen={editing}
        programName={match.instrument_name}
        entries={entries}
        profile={result.profile}
        extracted={extracted}
        onClose={() => setEditing(false)}
        onSave={(fields, answers) => {
          setEditing(false);
          onSaveEdits(fields, answers);
        }}
        onEditWholeProfile={() => {
          setEditing(false);
          onEditProfile();
        }}
      />

      <ChatDrawer isOpen={chatting} runId={result.run_id} match={match} onClose={() => setChatting(false)} />

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

      <section className="flex flex-col gap-4">
        <h2>{t.program.criteria}</h2>
        <div className="flex flex-col gap-2">
          <p className="text-lg font-semibold" data-testid="criteria-summary">
            {t.program.criteriaSummary(counts)}
          </p>
          <ul className="m-0 flex list-none flex-wrap gap-x-5 gap-y-1.5 p-0 text-sm text-fg-2" data-testid="criteria-legend" aria-label="Legende">
            {(["erfuellt", "annahme", "unbekannt", "nicht_erfuellt"] as const).map(s => (
              <li key={s} className="inline-flex items-center gap-1.5">
                <StatusSymbol state={s} size="sm" />
                {t.program.legend[s]}
              </li>
            ))}
          </ul>
        </div>
        {groups.map(g => (
          <div key={g.key} className="flex flex-col gap-1">
            <h3 className="text-base font-semibold">
              {t.program.groups[g.key]} <span className="font-normal text-fg-2">({g.items.length})</span>
            </h3>
            <ul className="m-0 flex list-none flex-col divide-y divide-line border-y border-line p-0">
              {g.items.map(item => (
                <CriterionRow key={item.criterion.criterion_id} item={item} n={numbered.indexOf(item.criterion.criterion_id) + 1} />
              ))}
            </ul>
          </div>
        ))}
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

/** One checklist row: criterion and reason over the full width, the source chip small below. */
function CriterionRow({ item: { criterion: c, open }, n }: { item: CriteriaItem; n: number }) {
  return (
    <li id={criterionAnchor(c)} className="grid scroll-mt-24 grid-cols-[24px_minmax(0,1fr)] gap-x-3 py-3">
      <span className="pt-0.5">{c.state !== "nicht_anwendbar" && <StatusSymbol state={c.state} />}</span>
      <div className="flex min-w-0 flex-col items-start gap-1">
        <span className="font-semibold" data-testid="criterion-text">
          {c.text}
        </span>
        <span className="text-fg-2">{c.reason}</span>
        {open && open.inputs.length > 0 && <span className="text-sm text-primary-ink">{whyOpen(open)}</span>}
        <span className="max-w-full sm:max-w-md">
          <SourceChip source={c.source} n={n} />
        </span>
      </div>
    </li>
  );
}

function whyOpen({ why }: OpenCriterion): string {
  if (why.kind === "fehlt") return t.program.whyMissing(why.fields.map(fieldLabel).join(", "));
  if (why.kind === "widerspruch") return t.program.whyConflict(why.conflicts.map(c => fieldLabel(c.field)).join(", "));
  if (why.kind === "reicht_nicht") return `${t.program.whyNotEnough}: ${why.reason}`;
  return t.program.whyApplication;
}

/** The open program is no longer in the result after a re-run: say so and why. */
export function ProgramGone({ text, onBack }: { text: string; onBack: () => void }) {
  return (
    <Page>
      <button type="button" onClick={onBack} className="-mb-4 inline-flex items-center gap-1.5 self-start text-sm font-semibold text-primary-ink underline decoration-primary-ink/30 underline-offset-4 hover:decoration-primary-ink">
        <ArrowLeft aria-hidden="true" className="size-4" />
        {t.program.back}
      </button>
      <p className="text-lg" data-testid="program-gone">
        {text}
      </p>
    </Page>
  );
}
