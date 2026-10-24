"""Follow-up chat about one instrument of one run: one LLM call, then code post-checks.

The only context is the run's result for this instrument (profile, criteria, gaps, deadline,
plan entries, warnings) and the full program file. No web, no general knowledge about
programs.

Post-checks on every answer:
1. out of scope → fixed fallback text plus the program's contact
2. citations must name a source of the program and a locator that occurs in the program file;
   any unknown citation is dropped and the basis becomes `nicht_belegt`; `belegt` without a
   valid citation becomes `abgeleitet`
3. binding wording ("Sie haben Anspruch", "Sie erhalten") → fallback
4. `belegt`/`abgeleitet`: every number (amounts, rates, dates) must occur in the context,
   otherwise fallback
5. `allgemein` (general term explanation): no amounts, rates or dates and no program name,
   otherwise fallback; never carries citations
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from app.agent.text import squash
from app.knowledge_base.flat import FlatInstrument
from app.knowledge_base.loader import KnowledgeBase
from app.llm.client import LLMClient
from app.llm.prompts import load_prompt
from app.llm.schema import LLMOutput
from app.models.contract import (
    ChatMessage,
    ChatResponse,
    ChatResponseContact,
    ChatSuggestions,
    ChatSuggestionsQuestion,
    InstrumentMatch,
    InstrumentRef,
    RunResult,
    SourceLink,
)

FALLBACK = (
    "Dazu kann ich keine gesicherte Auskunft geben. Bitte wenden Sie sich an die Ansprechstelle."
)
MAX_HISTORY = 20
MAX_SUGGESTIONS = 3

type Basis = Literal["belegt", "abgeleitet", "allgemein", "nicht_belegt"]


class ChatTargetNotFoundError(KeyError):
    """The instrument is not among the checked matches of this run."""


class Citation(LLMOutput):
    source_id: str
    locator: str | None


class ChatOutput(LLMOutput):
    out_of_scope: bool
    answer: str
    basis: Literal["belegt", "abgeleitet", "allgemein", "nicht_belegt"]
    citations: list[Citation]


@dataclass(frozen=True)
class ChatTarget:
    result: RunResult
    match: InstrumentMatch
    item: FlatInstrument


def find_target(result: RunResult, ref: InstrumentRef, kb: KnowledgeBase) -> ChatTarget:
    match = next(
        (
            m
            for m in result.matches
            if m.program_id == ref.program_id and m.instrument_id == ref.instrument_id
        ),
        None,
    )
    item = kb.find(ref)
    if match is None or match.status != "fertig" or item is None:
        raise ChatTargetNotFoundError(f"{ref.program_id}:{ref.instrument_id}")
    return ChatTarget(result, match, item)


async def answer(target: ChatTarget, messages: list[ChatMessage], llm: LLMClient) -> ChatResponse:
    context = chat_context(target)
    history = [{"rolle": m.role, "text": m.text} for m in messages[-MAX_HISTORY:]]
    user = json.dumps(
        {"kontext": context, "verlauf": history[:-1], "frage": history[-1]["text"]},
        ensure_ascii=False,
        indent=1,
    )
    output = await llm.structured(
        task="chat",
        system=load_prompt("chat"),
        user=user,
        output=ChatOutput,
        tier="main",
        effort="low",
    )
    return post_check(target, output, json.dumps(context, ensure_ascii=False))


def _contact(target: ChatTarget) -> ChatResponseContact | None:
    contact = next((c for c in target.item.program.contacts if c.name), None)
    if contact is None:
        return None
    return ChatResponseContact(
        name=contact.name or "",
        role=contact.role,
        email=contact.email,
        phone=contact.phone,
        url=contact.url,
    )


def _fallback(target: ChatTarget) -> ChatResponse:
    return ChatResponse(
        answer=FALLBACK, basis="nicht_belegt", citations=[], contact=_contact(target)
    )


def post_check(target: ChatTarget, output: ChatOutput, context: str) -> ChatResponse:
    if output.out_of_scope or not output.answer.strip() or binding(output.answer):
        return _fallback(target)
    basis: Basis = output.basis
    if basis == "nicht_belegt":
        return _fallback(target)
    if basis == "allgemein":
        program = target.item.program
        names = [program.name, program.short_name, target.match.instrument_name]
        if looks_like_figure(output.answer) or any(
            n and squash(n) in squash(output.answer) for n in names
        ):
            return _fallback(target)
        return ChatResponse(answer=output.answer, basis="allgemein", citations=[], contact=None)

    if not (
        numbers(output.answer) <= numbers(context) and percents(output.answer) <= percents(context)
    ):
        return _fallback(target)
    citations, all_known = resolve_citations(target.item, output.citations)
    if not all_known:
        basis = "nicht_belegt"
    elif basis == "belegt" and not citations:
        basis = "abgeleitet"
    contact = _contact(target) if basis == "nicht_belegt" else None
    return ChatResponse(answer=output.answer, basis=basis, citations=citations, contact=contact)


def resolve_citations(
    item: FlatInstrument, citations: list[Citation]
) -> tuple[list[SourceLink], bool]:
    """Known citations as links, and whether every citation was known."""
    sources = {s.id: s for s in item.program.sources}
    locators = known_locators(item)
    links: list[SourceLink] = []
    all_known = True
    for citation in citations:
        source = sources.get(citation.source_id)
        locator = citation.locator.strip() if citation.locator else None
        known = locators.get(citation.source_id, {})
        if source is None or (locator and squash(locator) not in known):
            all_known = False
            continue
        locator = known[squash(locator)] if locator else None
        link = SourceLink(title=source.title, url=source.url, locator=locator)
        if link not in links:
            links.append(link)
    return links, all_known


def known_locators(item: FlatInstrument) -> dict[str, dict[str, str]]:
    """Every locator in the program file per source id, keyed by its squashed form."""
    found: dict[str, dict[str, str]] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("source_id"), str) and isinstance(node.get("locator"), str):
                locator = node["locator"]
                found.setdefault(node["source_id"], {})[squash(locator)] = locator
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(item.program.model_dump(mode="json", by_alias=True))
    return found


# Binding statements about eligibility or money. Orientation only, never a promise.
BINDING = re.compile(
    r"\b(sie haben|haben sie) (einen |den )?(rechts)?anspruch\b"
    r"|\b(sie erhalten|erhalten sie|sie bekommen|bekommen sie)\b"
    r"|\b(sie sind|sind sie) (förder)?berechtigt\b"
    r"|\b(ist|sind|wird|werden) (ihnen )?(garantiert|zugesichert|sicher bewilligt)\b",
    re.IGNORECASE,
)


def binding(text: str) -> bool:
    return BINDING.search(text) is not None


# Apostrophe, typographic apostrophe, (narrow) no-break space and space as thousands separators.
SEPARATORS = "'" + chr(0x2019) + chr(0xA0) + chr(0x202F) + " "
THOUSANDS = re.compile(rf"(?<=\d)[{SEPARATORS}](?=\d{{3}}\b)")


def numbers(text: str) -> set[str]:
    """Every digit group as a number without leading zeros; 15'000 and 15000 are the same."""
    return {str(int(n)) for n in re.findall(r"\d+", THOUSANDS.sub("", text))}


PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:%|prozent\b)|_pct\"\s*:\s*(\d+(?:\.\d+)?)", re.I)


def percents(text: str) -> set[float]:
    """Rates written as "30 %" or stored as `rate_pct: 30`. Stricter than `numbers`: a rate
    must occur as a rate, not just as any number (e.g. a Randnummer)."""
    return {float((a or b).replace(",", ".")) for a, b in PERCENT.findall(text)}


MONTHS = "januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember"
FIGURE = re.compile(
    r"%|\bprozent\b|\bchf\b|\bfr\.|€|\$|\beur\b|\bmio\b|\bmrd\b"
    r"|\d\s*(franken|rappen|tage|tagen|wochen|monate|monaten|jahre|jahren)\b"
    r"|\b\d{1,2}\.\s?\d{1,2}\.(\s?\d{2,4})?"
    r"|\b\d{4}-\d{2}"
    r"|\b(19|20)\d{2}\b"
    rf"|\b\d{{1,2}}\.\s?({MONTHS})\b",
    re.IGNORECASE,
)


def looks_like_figure(text: str) -> bool:
    """An amount, rate, date or deadline, which a general explanation must not contain."""
    return FIGURE.search(text) is not None


def chat_context(target: ChatTarget) -> dict[str, Any]:
    result, match, item = target.result, target.match, target.item
    ref = (match.program_id, match.instrument_id)

    def mine(program_id: str, instrument_id: str | None) -> bool:
        return program_id == ref[0] and (instrument_id is None or instrument_id == ref[1])

    shown = {
        (m.program_id, m.instrument_id): m.instrument_name
        for m in result.matches
        if m.fit in ("passt_gut", "passt_mit_anpassung")
    }
    plan = result.plan
    warnings = []
    for w in plan.warnings if plan else []:
        if any(mine(i.program_id, i.instrument_id) for i in w.items):
            warning = w.model_dump(mode="json")
            warning["andere_angebote"] = [
                shown.get((i.program_id, i.instrument_id), i.program_id)
                for i in w.items
                if not mine(i.program_id, i.instrument_id)
            ]
            warnings.append(warning)
    locators = known_locators(item)
    return {
        "angebot": match.model_dump(mode="json", exclude={"status", "error", "source_checked"}),
        "profil": {
            "zusammenfassung": result.profile.summary,
            "felder": {
                name: {"wert": f.value, "status": f.status}
                for name, f in result.profile.fields.items()
                if f.status != "fehlt"
            },
            "fehlende_felder": sorted(
                n for n, f in result.profile.fields.items() if f.status == "fehlt"
            ),
        },
        "fahrplan": [
            e.model_dump(mode="json")
            for e in (plan.timeline if plan else [])
            if mine(e.program_id, e.instrument_id)
        ],
        "naechste_schritte": [
            s.model_dump(mode="json")
            for s in (plan.next_steps if plan else [])
            if s.program_id and mine(s.program_id, s.instrument_id)
        ],
        "kombinationswarnungen": warnings,
        "weitere_gezeigte_angebote": [
            {"program_id": p, "instrument_id": i, "name": name}
            for (p, i), name in shown.items()
            if (p, i) != ref
        ],
        "quellen": [
            {
                "source_id": s.id,
                "titel": s.title,
                "fundstellen": sorted(locators.get(s.id, {}).values()),
            }
            for s in item.program.sources
        ],
        "programmdatei": item.program.model_dump(mode="json", by_alias=True, exclude_none=True),
    }


def suggestions(target: ChatTarget) -> ChatSuggestions:
    """Up to three questions from the result, most specific first. Code only."""
    match, result = target.match, target.result
    name = match.instrument_name
    found: list[ChatSuggestionsQuestion] = []

    def add(text: str, topic: str) -> None:
        found.append(ChatSuggestionsQuestion(text=text, topic=topic))

    if match.fit == "passt_nicht":
        add(f"Warum passt «{name}» nicht?", "passung")
    elif match.fit == "passt_mit_anpassung" and any(g.type == "anpassung" for g in match.gaps):
        add(f"Was müsste ich ändern, damit «{name}» passt?", "passung")

    open_muss = next(
        (
            c
            for state in ("nicht_erfuellt", "unbekannt")
            for c in match.criteria
            if c.kind == "muss" and c.state == state
        ),
        None,
    )
    if open_muss is not None:
        add(f"Was fehlt noch bei «{short_text(open_muss.text)}»?", "offen")

    plan = result.plan
    for warning in plan.warnings if plan else []:
        others = [
            m.instrument_name
            for i in warning.items
            for m in result.matches
            if (i.program_id, i.instrument_id) != (match.program_id, match.instrument_id)
            and m.program_id == i.program_id
            and (i.instrument_id is None or m.instrument_id == i.instrument_id)
            and m.fit in ("passt_gut", "passt_mit_anpassung")
        ]
        mine = any(
            i.program_id == match.program_id and i.instrument_id in (None, match.instrument_id)
            for i in warning.items
        )
        if mine and others:
            add(f"Kann ich «{name}» mit «{others[0]}» kombinieren?", "kombination")
            break

    if match.deadline.next_date is not None:
        add(f"Was muss bis zum {match.deadline.next_date:%d.%m.%Y} eingereicht sein?", "frist")
    elif match.deadline.rule:
        add("Wann muss ich das Gesuch einreichen?", "frist")

    return ChatSuggestions(questions=found[:MAX_SUGGESTIONS])


def short_text(text: str, limit: int = 60) -> str:
    """The first clause of a criterion text without parentheses, at most `limit` characters."""
    text = re.sub(r"\s*\([^)]*\)", "", text)
    clause = re.split(r"[:;]", text, maxsplit=1)[0].strip().rstrip(".,")
    if len(clause) <= limit:
        return clause
    return clause[:limit].rsplit(" ", 1)[0] + " …"
