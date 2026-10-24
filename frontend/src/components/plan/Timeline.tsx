import type { CombinationWarning, FundingPlan, RunResult, TimelineEntry } from "../../api/contract";
import { daysUntil, formatDateShort } from "../../lib/format";
import { host, sameStep, uniqueWarnings } from "../../lib/plan";
import { isAdvisory } from "../../lib/results";
import { PHASE_LABEL, t } from "../../text/de-CH";
import { COST_YEAR, urgencyOf, URGENCY_TEXT } from "../results/parts";
import { External, Mail, Phone } from "../ui/icons";
import { WarningNote } from "./WarningNote";

type Contact = FundingPlan["contacts"][number];

export interface PlanItem {
  key: string;
  programId: string;
  instrumentId: string | null;
  phase: TimelineEntry["phase"];
  program: string;
  title: string;
  /** One line per merged step, in order. */
  actions: string[];
  date: string | null;
  /** The date, or the rule text from the knowledge base when there is no date. */
  when: string | null;
  link: string | null;
  warnings: CombinationWarning[];
  contact: Contact | null;
}

const PHASES: TimelineEntry["phase"][] = ["jetzt", "vor_projektstart", "gesuch"];

type Draft = PlanItem;

/**
 * Turns the plan into one list of steps, each action once:
 * - next steps merge into the matching timeline step (or become their own "jetzt" step)
 * - steps of the same instrument merge when they share a phase, or when the later one has no date and the
 *   instrument is advice (asking for the consultation and "applying" for it are the same action)
 * - each warning attaches to the submission it affects, each contact to the first step of its program
 * Contacts that fit no step are returned separately.
 */
export function planItems(result: RunResult): { items: PlanItem[]; looseContacts: Contact[] } {
  const plan = result.plan!;
  const matchOf = (programId: string, instrumentId: string | null) =>
    result.matches.find(m => m.program_id === programId && (!instrumentId || m.instrument_id === instrumentId));
  const programName = (id: string) => matchOf(id, null)?.program_name ?? id;
  const drafts: Draft[] = plan.timeline.map((e, i) => ({
    key: `tl${i}`,
    phase: e.phase,
    program: programName(e.program_id),
    title: e.title,
    // A claim on past costs (LIB) says which years the date stands for.
    actions: [e.action, e.date && e.date_rule && COST_YEAR.test(e.date_rule) ? e.date_rule : ""].filter(Boolean),
    date: e.date,
    when: e.date ? formatDateShort(e.date) : e.date_rule,
    link: null,
    warnings: [],
    contact: null,
    programId: e.program_id,
    instrumentId: e.instrument_id,
  }));

  for (const s of plan.next_steps) {
    const same = drafts.find(x => (!s.program_id || x.programId === s.program_id) && sameStep(`${x.title} ${x.actions.join(" ")}`, s.text));
    if (same) same.link ??= s.link;
    else
      drafts.push({
        key: s.text,
        phase: "jetzt",
        program: s.program_id ? programName(s.program_id) : "",
        title: s.text,
        actions: [],
        date: s.due,
        when: s.due ? formatDateShort(s.due) : null,
        link: s.link,
        warnings: [],
        contact: null,
        programId: s.program_id ?? "",
        instrumentId: s.instrument_id ?? null,
      });
  }

  const items: Draft[] = [];
  for (const d of drafts) {
    const match = d.instrumentId ? matchOf(d.programId, d.instrumentId) : undefined;
    const earlier = items.find(
      x =>
        x.instrumentId &&
        x.programId === d.programId &&
        x.instrumentId === d.instrumentId &&
        (x.phase === d.phase || (!d.date && match !== undefined && isAdvisory(match))),
    );
    if (!earlier) {
      items.push(d);
      continue;
    }
    earlier.actions.push(...d.actions.filter(a => !earlier.actions.includes(a)));
    earlier.link ??= d.link;
    earlier.date ??= d.date;
    earlier.when ??= d.when;
  }

  for (const w of uniqueWarnings(plan.warnings)) {
    const target =
      items.find(x => x.phase === "gesuch" && w.items.some(i => i.program_id === x.programId)) ?? [...items].reverse().find(x => w.items.some(i => i.program_id === x.programId));
    target?.warnings.push(w);
  }

  const looseContacts: Contact[] = [];
  for (const c of plan.contacts) {
    const match = result.matches.find(m => host(m.links.info) && host(m.links.info) === host(c.url));
    const target = items.find(x => (match && x.programId === match.program_id) || (x.link && host(x.link) === host(c.url)));
    if (target && !target.contact) target.contact = c;
    else looseContacts.push(c);
  }
  return { items, looseContacts };
}

interface Props {
  result: RunResult;
  items: PlanItem[];
  done: Set<string>;
  onToggle: (key: string) => void;
}

/** Labels closer than this (in % of the axis) move to a second row, so dates never overlap. */
const MIN_LABEL_GAP = 9;

/** Axis with today and the dated deadlines, then the steps grouped by phase. Phases without steps are left out. */
export function Timeline({ result, items, done, onToggle }: Props) {
  const dated = items.filter(i => i.date).sort((a, b) => a.date!.localeCompare(b.date!));
  const last = dated[dated.length - 1]?.date;
  const span = last ? Math.max(1, daysUntil(last, result.today)) : 1;
  // Today on the left; dated steps by their real distance from today.
  // Ends at 88 % so the last label (centred on its dot) stays inside the page.
  const position = (date: string) => 8 + Math.max(0, daysUntil(date, result.today) / span) * 80;
  const rows: number[] = [];
  dated.forEach((d, i) => {
    const previous = dated[i - 1];
    const close = previous && position(d.date!) - position(previous.date!) < MIN_LABEL_GAP;
    rows.push(close ? 1 - rows[i - 1] : 0);
  });
  const names = (w: CombinationWarning, own: PlanItem) =>
    w.items
      .filter(i => !(i.program_id === own.programId && (!i.instrument_id || i.instrument_id === own.instrumentId)))
      .map(i => result.matches.find(x => x.program_id === i.program_id && (!i.instrument_id || x.instrument_id === i.instrument_id))?.instrument_name ?? i.program_id);
  const phases = PHASES.map(p => ({ phase: p, list: items.filter(i => i.phase === p).sort((a, b) => (a.date ?? "9").localeCompare(b.date ?? "9")) })).filter(p => p.list.length > 0);

  return (
    <section className="flex flex-col gap-10">
      {dated.length > 0 && (
        <div className="relative h-24 select-none" aria-hidden="true">
          <span className="absolute top-12 right-0 left-0 h-0.5 origin-left animate-grow-x rounded-full bg-line-strong" />
          <span className="absolute top-3 left-0 flex animate-rise flex-col items-start">
            <span className="text-xs font-semibold text-primary-ink">
              {t.plan.today} {formatDateShort(result.today)}
            </span>
            <span className="mt-1 ml-1 size-0 border-x-[6px] border-t-[8px] border-x-transparent border-t-primary" />
          </span>
          {dated.map((d, i) => (
            <span key={d.key} className="absolute top-[43px] -translate-x-1/2 animate-pop" style={{ left: `${position(d.date!)}%`, animationDelay: `${300 + i * 150}ms` }}>
              <span className={`block size-3.5 rounded-full border-2 border-surface ring-1 ${urgencyOf(daysUntil(d.date!, result.today)) === "normal" ? "bg-fg ring-fg" : "bg-warn ring-warn"}`} />
            </span>
          ))}
          {dated.map((d, i) => (
            <span
              key={`${d.key}-label`}
              className={`absolute -translate-x-1/2 text-center text-xs font-semibold whitespace-nowrap tabular-nums ${rows[i] ? "top-16" : "top-0"}`}
              style={{ left: `${position(d.date!)}%` }}
            >
              {d.when}
              <span className="block font-normal text-fg-2">{d.program.split(/[,(:]/)[0].trim()}</span>
            </span>
          ))}
        </div>
      )}

      {phases.map(({ phase, list }) => (
        <section key={phase} className="flex flex-col gap-3" aria-label={PHASE_LABEL[phase]}>
          <h2 className="text-lg">{PHASE_LABEL[phase]}</h2>
          <ol className="m-0 flex list-none flex-col divide-y divide-line border-y border-line p-0">
            {list.map(item => {
              const days = item.date ? daysUntil(item.date, result.today) : null;
              const checked = done.has(item.key);
              return (
                <li key={item.key} className="grid animate-rise grid-cols-[20px_minmax(0,1fr)] gap-x-3 py-4 md:grid-cols-[20px_minmax(0,1fr)_9rem]">
                  <input
                    id={`plan-${item.key}`}
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggle(item.key)}
                    className="mt-1 size-4 accent-[var(--app-accent)]"
                  />
                  <div className="flex min-w-0 flex-col gap-1">
                    <label htmlFor={`plan-${item.key}`} className={`font-semibold ${checked ? "text-fg-muted line-through" : ""}`}>
                      {item.title}
                    </label>
                    <span className="text-sm text-fg-2">
                      {item.program}
                      {!item.date && item.when && ` · ${item.when}`}
                    </span>
                    {item.actions.map(a => (
                      <p key={a}>{a}</p>
                    ))}
                    {item.link && (
                      <a href={item.link} target="_blank" rel="noopener" className="inline-flex items-center gap-1 self-start text-sm font-semibold">
                        {t.plan.link} <External aria-hidden="true" className="size-3.5" />
                      </a>
                    )}
                    {item.contact && <ContactLine contact={item.contact} />}
                    {item.warnings.map(w => (
                      <WarningNote key={w.text} warning={w} others={names(w, item)} />
                    ))}
                  </div>
                  {item.date && (
                    <span className={`col-start-2 text-sm font-semibold tabular-nums md:col-start-3 md:row-start-1 md:text-right ${URGENCY_TEXT[urgencyOf(days)]}`}>{item.when}</span>
                  )}
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </section>
  );
}

export function ContactLine({ contact }: { contact: Contact }) {
  return (
    <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      <span className="text-fg-2">{contact.name}</span>
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
      {!contact.email && !contact.phone && contact.url && (
        <a href={contact.url} target="_blank" rel="noopener" className="inline-flex items-center gap-1">
          {t.plan.link} <External aria-hidden="true" className="size-3.5" />
        </a>
      )}
    </span>
  );
}
