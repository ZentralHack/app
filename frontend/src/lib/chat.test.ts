import { describe, expect, it } from "vitest";
import type { ChatResponse } from "../api/contract";
import { t } from "../text/de-CH";
import { ApiRequestError } from "../api/http";
import { chatChips, chatError, chatMessages, MAX_CHIPS, type Turn } from "./chat";

const STANDARD = t.chat.standard.map(s => s.text);

describe("chatChips", () => {
  it("shows all standard questions when nothing was generated", () => {
    expect(chatChips([]).map(c => c.text)).toEqual(STANDARD);
  });

  it("puts generated questions first and hides standard ones on the same topic", () => {
    const chips = chatChips([
      { text: "Was fehlt noch bei «Sitz im Kanton Luzern»?", topic: "offen" },
      { text: "Was muss bis zum 31.01.2027 eingereicht sein?", topic: "frist" },
    ]);
    expect(chips.map(c => c.text)).toEqual([
      "Was fehlt noch bei «Sitz im Kanton Luzern»?",
      "Was muss bis zum 31.01.2027 eingereicht sein?",
      "Welche Unterlagen brauche ich für das Gesuch?",
      "Kann ich das mit anderen Programmen kombinieren?",
      "Was bedeutet ein Begriff aus dem Ergebnis?",
    ]);
  });

  it("hides «Was fehlt mir noch» behind a question about the fit", () => {
    const chips = chatChips([{ text: "Was müsste ich ändern, damit «X» passt?", topic: "passung" }]);
    expect(chips.map(c => c.text)).not.toContain("Was fehlt mir noch für dieses Programm?");
  });

  it("never shows more than five chips", () => {
    const chips = chatChips([
      { text: "A", topic: "passung" },
      { text: "B", topic: "unterlagen" },
      { text: "C", topic: "kombination" },
    ]);
    expect(chips).toHaveLength(MAX_CHIPS);
    expect(chips.slice(0, 3).map(c => c.text)).toEqual(["A", "B", "C"]);
  });

  it("the term question pre-fills the input instead of sending", () => {
    const term = chatChips([]).find(c => c.text === "Was bedeutet ein Begriff aus dem Ergebnis?");
    expect(term?.prefill).toBe("Was bedeutet ");
    expect(chatChips([]).filter(c => c.prefill)).toHaveLength(1);
  });
});

describe("chatMessages", () => {
  const response: ChatResponse = { answer: "Antwort", basis: "belegt", citations: [], contact: null };

  it("sends answered turns as history and skips failed ones", () => {
    const turns: Turn[] = [
      { question: "Eins", response },
      { question: "Zwei", response: null, error: "Fehler" },
    ];
    expect(chatMessages(turns, "Drei")).toEqual([
      { role: "user", text: "Eins" },
      { role: "assistant", text: "Antwort" },
      { role: "user", text: "Drei" },
    ]);
  });

  it("keeps the request within 20 messages and ends with the question", () => {
    const turns: Turn[] = Array.from({ length: 15 }, (_, i) => ({ question: `F${i}`, response }));
    const messages = chatMessages(turns, "Neu");
    expect(messages.length).toBeLessThanOrEqual(20);
    expect(messages.at(-1)).toEqual({ role: "user", text: "Neu" });
    expect(messages[0].role).toBe("user");
  });
});

describe("chatError", () => {
  it.each([
    ["run_nicht_gefunden", 404, "Analyse abgelaufen, bitte neu starten", false],
    ["nicht_gefunden", 404, "Backend neu starten", false],
    ["ki_nicht_verfuegbar", 503, "KI nicht erreichbar", true],
    ["ki_antwort_ungueltig", 502, "keine gültige Antwort", true],
    ["netzwerk", 0, "Server nicht erreichbar", true],
    ["angebot_nicht_gefunden", 404, "nicht mehr im Ergebnis", false],
  ])("%s → specific message", (code, status, text, retry) => {
    const e = chatError(new ApiRequestError(status, code, "Diese Anfrage ist nicht möglich."));
    expect(e.message).toContain(text);
    expect(e.message).not.toBe("Diese Anfrage ist nicht möglich.");
    expect(e.retry).toBe(retry);
  });

  it("an unknown code keeps the server message and names the code", () => {
    expect(chatError(new ApiRequestError(418, "teekanne", "Kein Kaffee.")).message).toBe("Kein Kaffee. (Fehler teekanne)");
  });
});
