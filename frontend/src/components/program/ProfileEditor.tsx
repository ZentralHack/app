import { Drawer, Modal } from "@heroui/react";
import { useEffect, useState, type ReactNode } from "react";
import type { ProfileField, ProjectProfile, Question } from "../../api/contract";
import { fieldLabel, formatFieldValue } from "../../lib/format";
import { shortText, type Conflict, type EditorEntry } from "../../lib/openCriteria";
import { t } from "../../text/de-CH";
import { ProfileInput } from "../profile/ProfileInput";
import { DateAnswer, NumberAnswer } from "../questions/AnswerInputs";
import { Button } from "../ui/Button";

export interface EditorAnswer {
  question: Question;
  answer: string;
}

interface Props {
  isOpen: boolean;
  programName: string;
  entries: EditorEntry[];
  profile: ProjectProfile;
  /** The profile as read from the description, for contradictions. */
  extracted: ProjectProfile | null;
  onClose: () => void;
  onSave: (fields: Record<string, ProfileField>, answers: EditorAnswer[]) => void;
  onEditWholeProfile: () => void;
}

const DONT_KNOW = "Weiss nicht";
const EMPTY_FIELD: ProfileField = { value: null, status: "fehlt", origin: null, quote: null, note: null };

/** Wide screens get a drawer from the right, small screens a centered modal. */
function useWide() {
  const query = "(min-width: 768px)";
  const [wide, setWide] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const m = window.matchMedia(query);
    const on = () => setWide(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return wide;
}

/**
 * Inline editor on the program page. Offers only inputs that can change an open criterion: empty fields, the
 * criterion's own question (answered like a Rückfrage), contradictions to resolve, and free text to extend.
 * Closes with X, Esc or a click outside; focus stays inside while open.
 */
export function ProfileEditor({ isOpen, programName, entries, profile, extracted, onClose, onSave, onEditWholeProfile }: Props) {
  const wide = useWide();
  const [fields, setFields] = useState<Record<string, ProfileField>>({});
  const [answers, setAnswers] = useState<Record<string, EditorAnswer>>({});
  const changed = Object.keys(fields).length + Object.keys(answers).length > 0;

  const close = () => {
    setFields({});
    setAnswers({});
    onClose();
  };
  const save = () => {
    onSave(fields, Object.values(answers));
    setFields({});
    setAnswers({});
  };
  const setField = (name: string, field: ProfileField) => setFields(f => ({ ...f, [name]: field }));

  const header = (
    <div className="flex flex-col gap-1 pr-10">
      <span className="text-2xl font-semibold">{t.editor.title}</span>
      <span className="text-fg-2">{programName}</span>
    </div>
  );
  const body = (
    <div className="flex flex-col gap-2">
      <p className="text-fg-2">{t.editor.lead}</p>
      <ul className="m-0 flex list-none flex-col divide-y divide-line p-0">
        {entries.map(({ input, criteria }) => (
          <li key={input.key} className="flex flex-col gap-3 py-6" data-input={input.key}>
            {input.kind === "conflict" && <ConflictInput conflict={input.conflict} chosen={fields[input.conflict.field]} onChoose={f => setField(input.conflict.field, f)} />}
            {input.kind === "field" && (
              <ProfileInput name={input.name} field={fields[input.name] ?? profile.fields[input.name] ?? EMPTY_FIELD} original={extracted?.fields[input.name]} onChange={f => setField(input.name, f)} />
            )}
            {input.kind === "text" && (
              <>
                <ProfileInput name={input.name} field={fields[input.name] ?? profile.fields[input.name] ?? EMPTY_FIELD} onChange={f => setField(input.name, f)} />
                <span className="-mt-1 text-sm text-fg-2">{t.editor.extend}</span>
              </>
            )}
            {input.kind === "question" && (
              <QuestionInput
                question={input.question}
                answer={answers[input.question.id]?.answer}
                context={criteria.flatMap(c => c.profile_fields).filter((n, i, all) => all.indexOf(n) === i && !n.startsWith("rueckfrage_"))}
                profile={profile}
                onAnswer={answer => setAnswers(a => ({ ...a, [input.question.id]: { question: input.question, answer } }))}
              />
            )}
            <p className="text-sm text-fg-2">
              <span className="font-semibold text-fg">{t.editor.why}: </span>
              {criteria.map(c => `«${shortText(c.text)}»`).join(" ")}
            </p>
          </li>
        ))}
      </ul>
      <button type="button" onClick={onEditWholeProfile} className="self-start text-sm font-semibold text-primary-ink underline decoration-primary-ink/30 underline-offset-4 hover:decoration-primary-ink">
        {t.editor.wholeProfile}
      </button>
    </div>
  );
  const footer = (
    <>
      {!changed && <span className="mr-auto text-sm text-fg-2">{t.editor.unchanged}</span>}
      <Button variant="secondary" onClick={close}>
        {t.editor.cancel}
      </Button>
      <Button disabled={!changed} onClick={save}>
        {t.editor.save}
      </Button>
    </>
  );

  if (wide) {
    return (
      <Drawer.Backdrop isOpen={isOpen} onOpenChange={open => !open && close()}>
        <Drawer.Content placement="right">
          <Drawer.Dialog aria-label={t.editor.title} className="w-full sm:w-[36rem]" data-testid="profile-editor">
            <Drawer.CloseTrigger aria-label={t.editor.close} />
            <Drawer.Header>{header}</Drawer.Header>
            <Drawer.Body>{body}</Drawer.Body>
            <Drawer.Footer className="flex flex-wrap items-center justify-end gap-3 border-t border-line pt-4">{footer}</Drawer.Footer>
          </Drawer.Dialog>
        </Drawer.Content>
      </Drawer.Backdrop>
    );
  }
  return (
    <Modal.Backdrop isOpen={isOpen} onOpenChange={open => !open && close()}>
      <Modal.Container placement="center" scroll="inside" size="lg">
        <Modal.Dialog aria-label={t.editor.title} data-testid="profile-editor">
          <Modal.CloseTrigger aria-label={t.editor.close} />
          <Modal.Header>{header}</Modal.Header>
          <Modal.Body>{body}</Modal.Body>
          <Modal.Footer className="flex flex-wrap items-center justify-end gap-3 border-t border-line pt-4">{footer}</Modal.Footer>
        </Modal.Dialog>
      </Modal.Container>
    </Modal.Backdrop>
  );
}

const ORIGIN: Record<string, string> = { text: t.editor.fromText, formular: t.profile.fromForm, rueckfrage: t.profile.fromAnswer, korrektur: t.profile.edited };

/** Where a value comes from, in words. */
function originOf(f: ProfileField) {
  if (f.status === "annahme") return t.editor.assumedSource;
  return (f.origin && ORIGIN[f.origin]) ?? "";
}

function Choice({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onClick}
      className="flex w-full flex-col items-start gap-0.5 rounded-lg border border-line-strong bg-surface px-4 py-3 text-left transition-colors hover:border-primary aria-checked:border-primary aria-checked:bg-primary-soft"
    >
      {children}
    </button>
  );
}

/** Description and field disagree: both side by side, the user picks the one that is right. */
function ConflictInput({ conflict, chosen, onChoose }: { conflict: Conflict; chosen: ProfileField | undefined; onChoose: (f: ProfileField) => void }) {
  const { field, fromText, current } = conflict;
  const pickedText = chosen?.origin === "text";
  const pickedCurrent = chosen !== undefined && !pickedText;
  return (
    <div className="flex flex-col gap-3">
      <span className="text-sm font-semibold">{t.editor.conflict(fieldLabel(field))}</span>
      <div role="radiogroup" aria-label={t.editor.conflict(fieldLabel(field))} className="grid gap-2 sm:grid-cols-2">
        <Choice selected={pickedText} onClick={() => onChoose({ ...fromText })}>
          <span className="text-sm text-fg-2">{t.editor.fromText}</span>
          <span className="font-semibold">{formatFieldValue(field, fromText)}</span>
          <span className="text-sm text-fg-2">«{fromText.quote}»</span>
        </Choice>
        <Choice selected={pickedCurrent} onClick={() => onChoose({ ...current, note: t.editor.textOutdated })}>
          <span className="text-sm text-fg-2">{t.profile.edited}</span>
          <span className="font-semibold">{formatFieldValue(field, current)}</span>
          <span className="text-sm text-fg-2">{t.editor.keepCorrection}</span>
        </Choice>
      </div>
    </div>
  );
}

/** The criterion's own question, answered like a Rückfrage, with what the profile says so far. */
function QuestionInput({
  question,
  answer,
  context,
  profile,
  onAnswer,
}: {
  question: Question;
  answer: string | undefined;
  context: string[];
  profile: ProjectProfile;
  onAnswer: (a: string) => void;
}) {
  const known = context.map(n => [n, profile.fields[n]] as const).filter(([, f]) => f && f.status !== "fehlt");
  return (
    <div className="flex flex-col gap-3">
      <span className="font-semibold">{question.text}</span>
      {known.length > 0 && (
        <p className="text-sm text-fg-2">
          {t.editor.inProfile}{" "}
          {known.map(([n, f], i) => (
            <span key={n}>
              {i > 0 && "; "}
              {fieldLabel(n)}: <b className="font-semibold text-fg">{formatFieldValue(n, f!)}</b>
              {originOf(f!) && ` (${originOf(f!)})`}
            </span>
          ))}
        </p>
      )}
      {question.input === "auswahl" ? (
        <div role="radiogroup" aria-label={question.text} className="flex flex-col gap-2">
          {question.options.map(o => (
            <Choice key={o} selected={answer === o} onClick={() => onAnswer(o)}>
              <span>{o}</span>
            </Choice>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {question.input === "zahl" ? (
            <NumberAnswer question={question} value={answer && answer !== DONT_KNOW ? answer : ""} onChange={onAnswer} autoFocus={false} />
          ) : (
            <DateAnswer value={answer && answer !== DONT_KNOW ? answer : ""} onChange={v => v && onAnswer(v)} />
          )}
          {question.options.includes(DONT_KNOW) && (
            <Choice selected={answer === DONT_KNOW} onClick={() => onAnswer(DONT_KNOW)}>
              <span>{DONT_KNOW}</span>
            </Choice>
          )}
        </div>
      )}
    </div>
  );
}
