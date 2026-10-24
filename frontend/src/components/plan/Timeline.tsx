import type { CombinationWarning, FundingPlan, RunResult, TimelineEntry } from "../../api/contract";
import { daysUntil, formatDateShort } from "../../lib/format";
import { PHASE_LABEL, t } from "../../text/de-CH";
import { urgencyOf, URGENCY_TEXT } from "../results/parts";
import { matchTitle } from "../results/ResultCard";
import { host, sameStep } from "../../lib/plan";
import { WarningNote } from "./WarningNote";

type Contact = FundingPlan["contacts"][number];

export interface PlanItem {
  key: string;
  phase: TimelineEntry["phase"];
  program: string;
  title: string;
  action: string | null;
  date: string | null;
  when: string | null;
  link: string | null;
  warnings: CombinationWarning[];
  contact: Contact | null;
}

const PHASES: TimelineEntry["phase"][] = ["jetzt", "vor_projektstart", "gesuch"];

type Draft = PlanItem & { programId: string };

/**
 * Turns the plan into one list of items: next steps merge into the matching timeline item (or become their own
 * "jetzt" item), each warning attaches to the submission it affects, each contact to the first step of its program.
 * Contacts that fit no step are returned separately.
 */
export function planItems(result: RunResult): { items: PlanItem[]; looseContacts: Contact[] } {
  const plan = result.plan!;
  const programName = (id: string) => result.matches.find(m => m.program_id === id)?.program_name ?? id;
  const items: Draft[] = plan.timeline.map((e, i) => ({
    key: `tl${i}`,
    phase: e.phase,
    program: programName(e.program_id),
    title: e.title,
    action: e.action,
    date: e.date,
    when: e.date ? formatDateShort(e.date) : e.date_rule,
    link: null,
    warnings: [],
    contact: null,
    programId: e.program_id,
  }));

  for (const s of plan.next_steps) {
    const same = items.find(x => (!s.program_id || x.programId === s.program_id) && sameStep(`${x.title} ${x.action ?? ""}`, s.text));
    if (same) same.link ??= s.link;
    else
      items.push({ key: s.text, phase: "jetzt", program: s.program_id ? programName(s.program_id) : "", title: s.text, action: null, date: s.due, when: s.due ? formatDateShort(s.due) : null, link: s.link, warnings: [], contact: null, programId: s.program_id ?? "" });
  }

  for (const w of plan.warnings) {
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

/** Horizontal axis with a today marker and dated ticks, the steps below in their phase column. */
export function Timeline({ result, items, done, onToggle }: Props) {
  const dated = items.filter(i => i.date).sort((a, b) => a.date!.localeCompare(b.date!));
  const first = dated[0]?.date;
  const last = dated[dated.length - 1]?.date;
  const span = first && last ? Math.max(1, daysUntil(last, first)) : 1;
  // Dated items sit on the last third of the axis, spread by their real distance in time.
  const position = (date: string) => 72 + (first ? (daysUntil(date, first) / span) * 24 : 0);
  const names = (w: CombinationWarning) => w.items.map(i => {
    const m = result.matches.find(x => x.program_id === i.program_id && (!i.instrument_id || x.instrument_id === i.instrument_id));
    return m ? matchTitle(m) : i.program_id;
  });

  return (
    <section className="flex flex-col gap-8">
      <div className="relative h-20 select-none" aria-hidden="true">
        <span className="absolute top-9 right-0 left-0 h-0.5 origin-left animate-grow-x rounded-full bg-line-strong" />
        <span className="absolute top-0 left-0 flex animate-rise flex-col items-start">
          <span className="text-xs font-semibold text-primary-ink">
            {t.plan.today} {formatDateShort(result.today)}
          </span>
          <span className="mt-1 ml-1 size-0 border-x-[6px] border-t-[8px] border-x-transparent border-t-primary" />
        </span>
        {PHASES.map((p, i) => (
          <span key={p} className="absolute top-12 animate-rise text-sm font-semibold text-fg-2" style={{ left: `${i * 34}%`, animationDelay: `${i * 150}ms` }}>
            {PHASE_LABEL[p]}
          </span>
        ))}
        {dated.map((d, i) => (
          <span key={d.key} className="absolute top-[30px] flex -translate-x-1/2 animate-pop flex-col items-center" style={{ left: `${position(d.date!)}%`, animationDelay: `${300 + i * 150}ms` }}>
            <span className="size-3.5 rounded-full border-2 border-surface bg-fg ring-1 ring-fg" />
          </span>
        ))}
        {dated.map(d => (
          <span key={`${d.key}-label`} className="absolute top-0 -translate-x-1/2 text-xs font-semibold tabular-nums" style={{ left: `${position(d.date!)}%` }}>
            {d.when}
          </span>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-x-10 gap-y-8 md:grid-cols-3">
        {PHASES.map(p => {
          const list = items.filter(i => i.phase === p).sort((a, b) => (a.date ?? "").localeCompare(b.date ?? ""));
          return (
            <ol key={p} className="m-0 flex list-none flex-col divide-y divide-line p-0" aria-label={PHASE_LABEL[p]}>
              <li className="pb-2 text-sm font-semibold text-fg-2 md:hidden">{PHASE_LABEL[p]}</li>
              {list.map(item => {
                const days = item.date ? daysUntil(item.date, result.today) : null;
                const checked = done.has(item.key);
                return (
                  <li key={item.key} className="flex animate-rise gap-3 py-3 first:pt-0">
                    <input
                      id={`plan-${item.key}`}
                      type="checkbox"
                      checked={checked}
                      onChange={() => onToggle(item.key)}
                      className="mt-1 size-4 flex-none accent-[var(--app-accent)]"
                    />
                    <div className="flex min-w-0 flex-col gap-1">
                      <label htmlFor={`plan-${item.key}`} className={`font-semibold ${checked ? "text-fg-muted line-through" : ""}`}>
                        {item.title}
                      </label>
                      <span className="text-sm text-fg-2">
                        {item.program}
                        {item.when && (
                          <>
                            {" · "}
                            <span className={`font-semibold tabular-nums ${URGENCY_TEXT[urgencyOf(days)]}`}>{item.when}</span>
                          </>
                        )}
                      </span>
                      {item.action && <p className="text-sm">{item.action}</p>}
                      {item.link && (
                        <a href={item.link} target="_blank" rel="noopener" className="self-start text-sm font-semibold">
                          {t.plan.link} ↗
                        </a>
                      )}
                      {item.contact && <ContactLine contact={item.contact} />}
                      {item.warnings.map(w => (
                        <WarningNote key={w.text} warning={w} others={names(w)} />
                      ))}
                    </div>
                  </li>
                );
              })}
            </ol>
          );
        })}
      </div>
    </section>
  );
}

export function ContactLine({ contact }: { contact: Contact }) {
  return (
    <span className="flex flex-wrap gap-x-2 text-sm">
      <span className="text-fg-2">{contact.name}</span>
      {contact.email && <a href={`mailto:${contact.email}`}>{contact.email}</a>}
      {contact.phone && <a href={`tel:${contact.phone.replace(/\s/g, "")}`}>{contact.phone}</a>}
      {!contact.email && !contact.phone && contact.url && (
        <a href={contact.url} target="_blank" rel="noopener">
          {t.plan.link} ↗
        </a>
      )}
    </span>
  );
}
