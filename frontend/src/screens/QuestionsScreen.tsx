import { Calendar, DateField, DatePicker, InputGroup, TextField } from "@heroui/react";
import { parseDate, type DateValue } from "@internationalized/date";
import { useEffect, useRef, useState } from "react";
import { I18nProvider } from "react-aria-components";
import type { Question, QuestionSet } from "../api/contract";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/Button";
import { ConfirmMissing } from "../components/ui/ConfirmMissing";
import { programName } from "../content/programs";
import { formatDateShort, groupDigits } from "../lib/format";
import { t } from "../text/de-CH";

interface Props {
  questions: QuestionSet;
  answers: Record<string, string>;
  onAnswer: (questionId: string, answer: string | null) => void;
  busy: boolean;
  onBack: () => void;
  onNext: () => void;
}

const LETTERS = "ABCDEFGH";
const ADVANCE_MS = 380;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Answer as shown in the summary: dates in Swiss format, numbers with their unit. */
function displayAnswer(q: Question, answer: string) {
  if (q.input === "datum" && ISO_DATE.test(answer)) return formatDateShort(answer);
  if (q.input === "zahl" && /\d/.test(answer)) return q.unit === "CHF" ? `CHF ${answer}` : `${answer} ${q.unit ?? ""}`.trim();
  return answer;
}

/**
 * One question at a time. Button answers advance on their own; number and date answers
 * continue with Weiter or Enter. An assumption from the profile is shown as a suggestion; it only becomes an
 * answer when the user clicks it, so nothing is recorded that the user did not choose.
 * There is no skipping: every question needs an answer ("Weiss nicht" counts as one).
 */
export function QuestionsScreen({ questions, answers, onAnswer, busy, onBack, onNext }: Props) {
  const list = questions.questions;
  const [index, setIndex] = useState(0);
  const [clicked, setClicked] = useState(false);
  const [missing, setMissing] = useState<string[] | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const summary = index >= list.length;
  const q = summary ? null : list[index];
  const answer = q ? answers[q.id] : undefined;

  function goTo(i: number) {
    window.clearTimeout(timer.current);
    setClicked(false);
    setIndex(i);
  }

  function choose(option: string) {
    if (!q) return;
    onAnswer(q.id, option);
    setClicked(true);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => goTo(index + 1), ADVANCE_MS);
  }

  useEffect(() => () => window.clearTimeout(timer.current), []);


  useEffect(() => {
    if (!q) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || (e.target as HTMLElement).closest("input, [role=spinbutton]")) {
        if (e.key === "Enter" && answers[q.id]) goTo(index + 1);
        return;
      }
      const i = LETTERS.indexOf(e.key.toUpperCase());
      if (q.input === "auswahl" && i >= 0 && i < q.options.length) choose(q.options[i]);
      else if (e.key === "Enter" && answers[q.id]) goTo(index + 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (list.length === 0) {
    return (
      <Page>
        <h1>{t.questions.none}</h1>
        <div className="flex justify-between gap-3">
          <Button variant="secondary" onClick={onBack}>
            ← {t.common.back}
          </Button>
          <Button onClick={onNext} disabled={busy}>
            {t.questions.start} <span aria-hidden="true">→</span>
          </Button>
        </div>
      </Page>
    );
  }

  const progress = Math.min(index, list.length) / list.length;
  const open = list.filter(x => !answers[x.id]);
  // Live impact: which criteria the answers so far decide. "Weiss nicht" decides nothing.
  const decided = list.filter(x => answers[x.id] && answers[x.id] !== "Weiss nicht");
  const clarified = decided.reduce((n, x) => n + x.affects.length, 0);
  const names = (qs: Question[]) => [...new Set(qs.flatMap(x => x.affects.map(a => programName(a.program_id))))].join(", ");
  const typed = q && q.input !== "auswahl" && answer !== undefined && !q.options.includes(answer);
  // Weiter only where nothing advances by itself: typed answers, prefilled or revisited choices.
  const showNext = q && answer !== undefined && (typed || !clicked);

  return (
    <Page>
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-10">
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between text-sm font-semibold text-fg-2">
            <span>{summary ? t.questions.summary : t.questions.of(index + 1, list.length)}</span>
            <span>{t.questions.progress(list.filter(x => answers[x.id]).length, list.length)}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-line">
            <div className="h-full rounded-full bg-primary transition-[width] duration-500 ease-(--ease-app)" style={{ width: `${progress * 100}%` }} />
          </div>
          <div aria-live="polite" className="flex flex-col gap-0.5 pt-2">
            {clarified > 0 ? (
              <>
                <span className="text-xs font-semibold tracking-wide text-fg-2">{t.questions.impactLabel}</span>
                <span className="flex flex-wrap items-baseline gap-x-2">
                  <b key={clarified} className="animate-pop text-2xl font-semibold tabular-nums">
                    {t.questions.impact(clarified)}
                  </b>
                  <span className="text-fg-2">{t.questions.impactAt(names(decided))}</span>
                </span>
              </>
            ) : (
              <span className="text-fg-2">{t.questions.impactOpen(names(list))}</span>
            )}
          </div>
        </div>

        {q && (
          <section key={q.id} className="flex animate-rise flex-col gap-8">
            <div className="flex flex-col gap-3">
              <h1 className="text-3xl">{q.text}</h1>
              <p className="text-lg text-fg-2">{q.why}</p>
              {q.prefill && answer === undefined && <p className="text-sm font-semibold text-warn">{t.questions.suggested(q.prefill)}</p>}
            </div>

            <div className="flex flex-col gap-3">
              {q.input === "zahl" && <NumberAnswer question={q} value={typed ? answer! : ""} onChange={v => onAnswer(q.id, v || null)} />}
              {q.input === "datum" && <DateAnswer value={typed ? answer! : ""} onChange={v => onAnswer(q.id, v)} />}
              {q.options.map((option, i) => {
                const selected = answer === option;
                const suggested = answer === undefined && q.prefill === option;
                return (
                  <button
                    key={option}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => choose(option)}
                    className={`group flex h-12 w-full max-w-xl items-center gap-4 rounded-lg border bg-surface px-4 text-left ${suggested ? "border-dashed border-warn" : "border-line-strong"} transition-all hover:border-primary hover:bg-primary-soft active:scale-[.99] aria-pressed:border-primary aria-pressed:bg-primary-soft aria-pressed:shadow-[inset_0_0_0_1px_var(--app-accent)]`}
                  >
                    {q.input === "auswahl" && (
                      <kbd className="grid size-7 flex-none place-items-center rounded-md border border-line-strong bg-surface text-xs font-semibold text-fg-2 transition-colors group-aria-pressed:border-primary group-aria-pressed:bg-primary group-aria-pressed:text-white">
                        {LETTERS[i]}
                      </kbd>
                    )}
                    <span className="flex-1">{option}</span>
                    {selected && (
                      <span aria-hidden="true" className="animate-pop text-primary-ink">
                        ✓
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {q.input === "auswahl" && <p className="text-sm text-fg-2">{t.questions.keys}</p>}
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="ghost" onClick={() => (index === 0 ? onBack() : goTo(index - 1))}>
                ← {t.common.back}
              </Button>
              {showNext && (
                <Button className="ml-auto" onClick={() => goTo(index + 1)}>
                  {t.common.next} <span aria-hidden="true">→</span>
                </Button>
              )}
            </div>
          </section>
        )}

        {summary && (
          <section className="flex animate-rise flex-col gap-6">
            <div className="flex flex-col gap-3">
              <h1 className="text-3xl">{t.questions.summary}</h1>
              <p className="text-lg text-fg-2">{t.questions.summaryLead}</p>
            </div>
            <ol className="m-0 flex list-none flex-col divide-y divide-line rounded-xl border border-line bg-surface p-0">
              {list.map((x, i) => (
                <li key={x.id}>
                  <button type="button" onClick={() => goTo(i)} className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-bg">
                    <span className="grid size-8 flex-none place-items-center rounded-full bg-sunken text-sm font-semibold">{i + 1}</span>
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="font-semibold">{x.text}</span>
                      <span className={answers[x.id] ? "text-primary-ink" : "text-fg-muted"}>{answers[x.id] ? displayAnswer(x, answers[x.id]) : t.questions.unanswered}</span>
                    </span>
                    <span className="text-sm font-semibold text-primary-ink">{t.questions.change}</span>
                  </button>
                </li>
              ))}
            </ol>
            <div className="flex flex-wrap justify-between gap-3">
              <Button variant="secondary" onClick={() => goTo(list.length - 1)}>
                ← {t.common.back}
              </Button>
              <Button onClick={() => (open.length ? setMissing(open.map(x => x.text)) : onNext())} disabled={busy}>
                {t.questions.start} <span aria-hidden="true">→</span>
              </Button>
            </div>
          </section>
        )}
      </div>
      <ConfirmMissing
        missing={missing}
        onCancel={() => {
          setMissing(null);
          goTo(list.indexOf(open[0]));
        }}
        onConfirm={() => {
          setMissing(null);
          onNext();
        }}
      />
    </Page>
  );
}

/** Number answer with unit; CHF amounts get thousands separators while typing. */
function NumberAnswer({ question, value, onChange }: { question: Question; value: string; onChange: (v: string) => void }) {
  const chf = question.unit === "CHF";
  return (
    <TextField aria-label={question.text} value={value} onChange={v => onChange(chf ? groupDigits(v) : v.replace(/\D/g, "").slice(0, 9))} className="max-w-xs" autoFocus>
      <InputGroup>
        {chf && <InputGroup.Prefix>CHF</InputGroup.Prefix>}
        <InputGroup.Input inputMode="numeric" placeholder={t.questions.numberPlaceholder} className={chf ? "pl-2" : ""} />
        {question.unit && !chf && <InputGroup.Suffix>{question.unit}</InputGroup.Suffix>}
      </InputGroup>
    </TextField>
  );
}

/** Date answer: typed with automatic dots (TT.MM.JJJJ) or picked in the calendar. */
function DateAnswer({ value, onChange }: { value: string; onChange: (v: string | null) => void }) {
  return (
    <I18nProvider locale="de-CH">
      <DatePicker aria-label={t.profile.calendar} value={ISO_DATE.test(value) ? parseDate(value) : null} onChange={(d: DateValue | null) => onChange(d ? d.toString() : null)} className="max-w-xs">
        <DateField.Group fullWidth>
          <DateField.Input>{segment => <DateField.Segment segment={segment} />}</DateField.Input>
          <DateField.Suffix>
            <DatePicker.Trigger>
              <DatePicker.TriggerIndicator />
            </DatePicker.Trigger>
          </DateField.Suffix>
        </DateField.Group>
        <DatePicker.Popover>
          <Calendar aria-label={t.profile.calendar}>
            <Calendar.Header>
              <Calendar.YearPickerTrigger>
                <Calendar.YearPickerTriggerHeading />
              </Calendar.YearPickerTrigger>
              <Calendar.NavButton slot="previous" />
              <Calendar.NavButton slot="next" />
            </Calendar.Header>
            <Calendar.Grid>
              <Calendar.GridHeader>{day => <Calendar.HeaderCell>{day}</Calendar.HeaderCell>}</Calendar.GridHeader>
              <Calendar.GridBody>{date => <Calendar.Cell date={date} />}</Calendar.GridBody>
            </Calendar.Grid>
            <Calendar.YearPickerGrid>
              <Calendar.YearPickerGridBody>{({ year }) => <Calendar.YearPickerCell year={year} />}</Calendar.YearPickerGridBody>
            </Calendar.YearPickerGrid>
          </Calendar>
        </DatePicker.Popover>
      </DatePicker>
    </I18nProvider>
  );
}
