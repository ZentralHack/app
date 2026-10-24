import { Drawer, Modal } from "@heroui/react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { api, ApiRequestError } from "../../api";
import type { ChatResponse, InstrumentMatch } from "../../api/contract";
import { chatChips, chatMessages, historyKey, loadHistory, saveHistory, type Chip, type Turn } from "../../lib/chat";
import { t } from "../../text/de-CH";
import { SourceChip } from "../results/parts";
import { Button } from "../ui/Button";
import { Mail, Phone } from "../ui/icons";
import { Spinner } from "../ui/Spinner";
import { useWide } from "./ProfileEditor";

interface Props {
  isOpen: boolean;
  runId: string;
  match: InstrumentMatch;
  onClose: () => void;
}

/**
 * Follow-up chat about one Förderangebot, grounded only in this run's result and the program file. Same drawer
 * pattern as the profile editor: right side on wide screens, modal on small ones; X, Esc or a click outside closes.
 * The history stays in memory per run and instrument while the page is open.
 */
export function ChatDrawer({ isOpen, runId, match, onClose }: Props) {
  const wide = useWide();
  const ref = { program_id: match.program_id, instrument_id: match.instrument_id };
  const key = historyKey(runId, ref);
  const [turns, setTurns] = useState<Turn[]>(() => loadHistory(key));
  const [chips, setChips] = useState<Chip[]>(() => chatChips([]));
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => setTurns(loadHistory(key)), [key]);
  useEffect(() => {
    if (!isOpen) return;
    let live = true;
    api
      .chatSuggestions(runId, ref)
      .then(s => live && setChips(chatChips(s.questions)))
      .catch(() => live && setChips(chatChips([])));
    return () => {
      live = false;
    };
    // `ref` is rebuilt every render; the key covers it.
  }, [isOpen, key]);
  useEffect(() => end.current?.scrollIntoView({ block: "end", behavior: "smooth" }), [turns]);

  const update = (next: Turn[]) => {
    saveHistory(key, next);
    setTurns(next);
  };

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    const before = loadHistory(key);
    update([...before, { question: text, response: null }]);
    setDraft("");
    setBusy(true);
    try {
      const response = await api.chat(runId, ref, { messages: chatMessages(before, text) });
      update([...before, { question: text, response }]);
    } catch (e) {
      const error = e instanceof ApiRequestError ? e.message : String(e);
      update([...before, { question: text, response: null, error }]);
    } finally {
      setBusy(false);
    }
  }

  const pick = (chip: Chip) => {
    if (chip.prefill) {
      setDraft(chip.prefill);
      input.current?.focus();
    } else void ask(chip.text);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void ask(draft);
    }
  };
  const asked = new Set(turns.map(turn => turn.question));
  const open = chips.filter(c => !asked.has(c.text));

  const header = (
    <div className="flex flex-col gap-1 pr-10">
      <span className="text-2xl font-semibold">{t.chat.title}</span>
      <span className="text-fg-2">{match.instrument_name}</span>
    </div>
  );
  const body = (
    <div className="flex flex-col gap-5" data-testid="chat-log">
      {turns.length === 0 && <p className="text-fg-2">{t.chat.lead}</p>}
      {turns.map((turn, i) => (
        <div key={i} className="flex flex-col gap-2">
          <p className="max-w-[85%] self-end rounded-xl rounded-br-sm bg-primary-soft px-4 py-2.5 whitespace-pre-line text-fg">{turn.question}</p>
          {turn.response && <Answer response={turn.response} />}
          {!turn.response && !turn.error && (
            <span className="inline-flex items-center gap-2 text-sm text-fg-2">
              <Spinner />
              {t.chat.thinking}
            </span>
          )}
          {turn.error && (
            <p role="alert" className="text-sm text-error">
              {turn.error}
            </p>
          )}
        </div>
      ))}
      {open.length > 0 && (
        <div className="flex flex-col gap-2">
          {turns.length > 0 && <span className="text-sm font-semibold text-fg-2">{t.chat.suggested}</span>}
          <ul className="m-0 flex list-none flex-wrap gap-2 p-0" data-testid="chat-chips">
            {open.map(chip => (
              <li key={chip.text}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => pick(chip)}
                  className="rounded-full border border-line bg-surface px-3 py-1.5 text-left text-sm font-medium text-fg transition-colors hover:border-primary hover:bg-primary-soft hover:text-primary-ink disabled:opacity-50"
                >
                  {chip.text}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div ref={end} />
    </div>
  );
  const footer = (
    <div className="flex w-full flex-col gap-2">
      <div className="flex items-end gap-2">
        <textarea
          ref={input}
          rows={2}
          value={draft}
          maxLength={2000}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={onKey}
          placeholder={t.chat.placeholder}
          aria-label={t.chat.placeholder}
          className="min-h-11 flex-1 resize-none rounded-xl border border-line bg-surface px-3 py-2 text-fg outline-none focus:border-primary"
        />
        <Button disabled={busy || !draft.trim()} onClick={() => void ask(draft)}>
          {t.chat.send}
        </Button>
      </div>
      <p className="text-xs text-fg-2" data-testid="chat-disclaimer">
        {t.chat.disclaimer}
      </p>
    </div>
  );

  if (wide)
    return (
      <Drawer.Backdrop isOpen={isOpen} onOpenChange={o => !o && onClose()}>
        <Drawer.Content placement="right">
          <Drawer.Dialog aria-label={t.chat.title} className="w-full sm:w-[36rem]" data-testid="chat-drawer">
            <Drawer.CloseTrigger aria-label={t.chat.close} />
            <Drawer.Header>{header}</Drawer.Header>
            <Drawer.Body>{body}</Drawer.Body>
            <Drawer.Footer className="border-t border-line pt-4">{footer}</Drawer.Footer>
          </Drawer.Dialog>
        </Drawer.Content>
      </Drawer.Backdrop>
    );
  return (
    <Modal.Backdrop isOpen={isOpen} onOpenChange={o => !o && onClose()}>
      <Modal.Container placement="center" scroll="inside" size="lg">
        <Modal.Dialog aria-label={t.chat.title} data-testid="chat-drawer">
          <Modal.CloseTrigger aria-label={t.chat.close} />
          <Modal.Header>{header}</Modal.Header>
          <Modal.Body>{body}</Modal.Body>
          <Modal.Footer className="border-t border-line pt-4">{footer}</Modal.Footer>
        </Modal.Dialog>
      </Modal.Container>
    </Modal.Backdrop>
  );
}

/** One answer: text, source chips, the basis in small type, and the contact when nothing is certain. */
function Answer({ response: r }: { response: ChatResponse }) {
  return (
    <div className="flex max-w-[92%] flex-col items-start gap-2" data-basis={r.basis}>
      <p className="whitespace-pre-line">{r.answer}</p>
      {r.citations.length > 0 && (
        <div className="flex max-w-full flex-wrap gap-1.5">
          {r.citations.map(c => (
            <span key={`${c.url}${c.locator}`} className="max-w-full sm:max-w-xs">
              <SourceChip source={c} />
            </span>
          ))}
        </div>
      )}
      <span className="text-xs text-fg-2">{t.chat.basis[r.basis]}</span>
      {r.contact && (
        <p className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
          <b className="font-semibold">{t.chat.contact}:</b>
          <span>{r.contact.name}</span>
          {r.contact.email && (
            <a href={`mailto:${r.contact.email}`} className="inline-flex items-center gap-1">
              <Mail aria-hidden="true" className="size-3.5" />
              {r.contact.email}
            </a>
          )}
          {r.contact.phone && (
            <a href={`tel:${r.contact.phone.replace(/\s/g, "")}`} className="inline-flex items-center gap-1">
              <Phone aria-hidden="true" className="size-3.5" />
              {r.contact.phone}
            </a>
          )}
        </p>
      )}
    </div>
  );
}
