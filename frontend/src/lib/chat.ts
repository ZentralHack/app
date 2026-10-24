import type { ChatMessage, ChatRequest, ChatResponse, ChatSuggestions, InstrumentRef } from "../api/contract";
import { t } from "../text/de-CH";

type Topic = ChatSuggestions["questions"][number]["topic"];

export interface Chip {
  text: string;
  /** Put into the input instead of sending, for questions the user completes. */
  prefill?: string;
}

export interface Turn {
  question: string;
  /** Null while the answer is loading or after it failed. */
  response: ChatResponse | null;
  error?: string;
}

export const MAX_CHIPS = 5;

/** Generated questions first, then the standard ones whose topic no generated question covers, at most five. */
export function chatChips(generated: ChatSuggestions["questions"], standard: readonly { text: string; covers: readonly string[]; prefill?: string }[] = t.chat.standard): Chip[] {
  const topics = new Set<Topic>(generated.map(q => q.topic));
  const chips: Chip[] = generated.map(q => ({ text: q.text }));
  for (const s of standard) {
    if (s.covers.some(c => topics.has(c as Topic))) continue;
    chips.push(s.prefill ? { text: s.text, prefill: s.prefill } : { text: s.text });
  }
  return chips.slice(0, MAX_CHIPS);
}

/** The request history: every answered turn, then the new question. */
export function chatMessages(turns: Turn[], question: string): ChatRequest["messages"] {
  const history = turns.flatMap(turn =>
    turn.response
      ? [
          { role: "user" as const, text: turn.question },
          { role: "assistant" as const, text: turn.response.answer },
        ]
      : [],
  );
  // The backend reads only the last 20; keep the request small as well.
  const messages: ChatMessage[] = [...history.slice(-18), { role: "user", text: question }];
  return messages as ChatRequest["messages"];
}

/** Chat histories per run and instrument, kept in memory while the page is open. */
const histories = new Map<string, Turn[]>();

export const historyKey = (runId: string, ref: InstrumentRef) => `${runId}:${ref.program_id}:${ref.instrument_id}`;
export const loadHistory = (key: string): Turn[] => histories.get(key) ?? [];
export const saveHistory = (key: string, turns: Turn[]) => histories.set(key, turns);
