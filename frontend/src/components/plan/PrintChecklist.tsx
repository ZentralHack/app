import type { FundingPlan, RunResult } from "../../api/contract";
import { formatDateShort } from "../../lib/format";
import { PHASE_LABEL, t } from "../../text/de-CH";
import { planLabel, planPhases, type PlanItem } from "./Timeline";

type Contact = FundingPlan["contacts"][number];

/**
 * The Fahrplan for print and PDF: a checklist to tick off or pass on. Phases as headings, each step with an
 * empty box, date and deadline label, what to do, combination notes and the link written out.
 * Shown only in print; the screen keeps the interactive timeline.
 */
export function PrintChecklist({ result, items, contacts }: { result: RunResult; items: PlanItem[]; contacts: Contact[] }) {
  return (
    <section className="hidden flex-col gap-6 text-[11pt] leading-snug print:flex" data-testid="print-checklist">
      <p className="text-fg-2">{t.plan.printLead(formatDateShort(result.today))}</p>
      {planPhases(items).map(({ phase, list }) => (
        <section key={phase} className="flex flex-col gap-2">
          <h2 className="border-b border-line-strong pb-1 text-[14pt]">{PHASE_LABEL[phase]}</h2>
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {list.map(item => {
              const label = planLabel(item, result);
              return (
                <li key={item.key} className="grid break-inside-avoid grid-cols-[18px_minmax(0,1fr)] gap-x-3">
                  <span aria-hidden="true" className="mt-0.5 size-[13px] rounded-[2px] border-[1.5px] border-fg" />
                  <div className="flex flex-col gap-0.5">
                    <b className="font-semibold">{item.title}</b>
                    <span className="text-fg-2">
                      {[item.program, item.date ? [formatDateShort(item.date), label].filter(Boolean).join(", ") : item.when].filter(Boolean).join(" · ")}
                    </span>
                    {item.actions.map(a => (
                      <span key={a}>{a}</span>
                    ))}
                    {item.warnings.map(w => (
                      <span key={w.text}>
                        <b className="font-semibold">{t.program.warning}:</b> {w.text}
                      </span>
                    ))}
                    {item.link && <span className="break-all text-fg-2">{item.link}</span>}
                    {item.contact && <ContactText contact={item.contact} />}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      {contacts.length > 0 && (
        <section className="flex break-inside-avoid flex-col gap-2">
          <h2 className="border-b border-line-strong pb-1 text-[14pt]">{t.plan.contacts}</h2>
          {contacts.map(c => (
            <span key={c.name}>
              <b className="font-semibold">{c.role ?? c.name}</b> <ContactText contact={c} />
            </span>
          ))}
        </section>
      )}
    </section>
  );
}

function ContactText({ contact: c }: { contact: Contact }) {
  return <span className="text-fg-2">{[c.name, c.email, c.phone, !c.email && !c.phone ? c.url : null].filter(Boolean).join(" · ")}</span>;
}
