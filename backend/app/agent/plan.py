"""Step 6a-c (funding plan), pure code: timeline in three phases, combination warnings,
next steps and contacts. The LLM only rewrites texts afterwards (step 6d)."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.agent.prefilter import RULES
from app.agent.scoring import Fit
from app.knowledge_base.flat import FlatInstrument
from app.knowledge_base.loader import ANY_PROGRAM, KnowledgeBase
from app.models.contract import (
    CombinationWarning,
    FundingPlan,
    FundingPlanContact,
    Gap,
    NextStep,
    Rejected,
    TimelineEntry,
)
from app.models.program import CombinationRule, Program

FITTING: frozenset[Fit] = frozenset({"passt_gut", "passt_mit_anpassung"})
WARNING_TYPES = frozenset({"ausgeschlossen", "abzug", "bedingt"})
# When nothing fits: contacts of at most this many programs, the closest ones first.
CLOSEST_PROGRAMS = 3
# Among rejected programs of the same rule, cantonal offices are the best first contact.
LEVEL_ORDER = ("kanton", "region", "gemeinde", "bund", "stiftung", "privat", "international")

EVENT_LABELS = {
    "projektstart": "vor Projektstart",
    "baubeginn": "vor Baubeginn",
    "installationsbeginn": "vor Installationsbeginn",
    "inbetriebnahme": "nach Inbetriebnahme",
    "publikation": "nach Publikation",
    "gruendung": "nach Gründung",
}


@dataclass(frozen=True)
class PlanItem:
    """One scored instrument with its computed next deadline."""

    item: FlatInstrument
    fit: Fit
    gaps: list[Gap]
    next_deadline: date | None


def build_plan(items: list[PlanItem], rejected: list[Rejected], kb: KnowledgeBase) -> FundingPlan:
    fitting = [p for p in items if p.fit in FITTING]
    instruments = {p.item.key: p.item for p in fitting}
    timeline = _order_prerequisites(
        _now_entries(fitting) + _application_entries(fitting), list(instruments.values())
    )
    return FundingPlan(
        timeline=timeline,
        warnings=_warnings(list(instruments.values())),
        next_steps=[
            _next_step(entry, instruments[f"{entry.program_id}:{entry.instrument_id}"])
            for entry in timeline
        ],
        contacts=_contacts(_contact_programs(items, fitting, rejected, kb)),
    )


def _now_entries(fitting: list[PlanItem]) -> list[TimelineEntry]:
    """Levers to act on before any application, and steps recommended beforehand.

    `empfohlen_vorher`: the instrument that carries the rule is the earlier step, `with`
    names the later one (e.g. ITZ before Innosuisse). It is shown if both fit."""
    entries = [
        _entry("jetzt", p.item, f"{p.item.instrument.name}: so wird es passend", gap.lever)
        for p in fitting
        for gap in p.gaps
        if gap.type == "anpassung" and gap.lever
    ]
    instruments = [p.item for p in fitting]
    for owner in instruments:
        entries += [
            _entry("jetzt", owner, owner.instrument.name, rule.text)
            for rule in _rules(owner, "empfohlen_vorher")
            if _targets(rule, owner, instruments)
        ]
    return entries


def _application_entries(fitting: list[PlanItem]) -> list[TimelineEntry]:
    before_start, applications = [], []
    for p in fitting:
        spec = p.item.instrument.timing.deadline
        if spec.type == "vor_projektstart":
            event = (spec.relative and spec.relative.event) or "projektstart"
            before_start.append(
                _entry(
                    "vor_projektstart",
                    p.item,
                    _title(p.item),
                    "Gesuch einreichen.",
                    when=p.next_deadline,
                    rule=spec.rule or EVENT_LABELS[event],
                )
            )
        else:
            action = (
                "Unterlagen nach Abschluss einreichen."
                if spec.type == "nach_abschluss"
                else "Gesuch einreichen."
            )
            applications.append(
                _entry("gesuch", p.item, _title(p.item), action, p.next_deadline, spec.rule)
            )
    applications.sort(key=lambda e: e.date or date.max)
    return before_start + applications


def _title(item: FlatInstrument) -> str:
    return f"Gesuch {item.instrument.name}"


def _entry(
    phase: str,
    item: FlatInstrument,
    title: str,
    action: str | None,
    when: date | None = None,
    rule: str | None = None,
) -> TimelineEntry:
    return TimelineEntry(
        phase=phase,
        program_id=item.program.id,
        instrument_id=item.instrument.id,
        title=title,
        date=when,
        date_rule=rule,
        action=action or "",
    )


def _order_prerequisites(
    entries: list[TimelineEntry], instruments: list[FlatInstrument]
) -> list[TimelineEntry]:
    """An instrument with a `voraussetzung` comes after its prerequisite."""
    ordered = list(entries)
    for owner in instruments:
        for rule in _rules(owner, "voraussetzung"):
            for target in _targets(rule, owner, instruments):
                ordered = _move_after(ordered, owner, target)
    return ordered


def _move_after(
    entries: list[TimelineEntry], item: FlatInstrument, prerequisite: FlatInstrument
) -> list[TimelineEntry]:
    def belongs(entry: TimelineEntry, flat: FlatInstrument) -> bool:
        return (entry.program_id, entry.instrument_id) == (flat.program.id, flat.instrument.id)

    moving = [e for e in entries if belongs(e, item)]
    rest = [e for e in entries if not belongs(e, item)]
    last = max((i for i, e in enumerate(rest) if belongs(e, prerequisite)), default=None)
    if last is None:
        return entries
    return rest[: last + 1] + moving + rest[last + 1 :]


def _rules(owner: FlatInstrument, rule_type: str) -> list[CombinationRule]:
    return [r for r in owner.program.combination_rules if r.type == rule_type]


def _targets(
    rule: CombinationRule, owner: FlatInstrument, candidates: Iterable[FlatInstrument]
) -> list[FlatInstrument]:
    """Instruments a rule's `with` points to, among the candidates. A target that does
    not exist simply matches nothing, so dead references are ignored."""
    if rule.with_ == ANY_PROGRAM:
        return [c for c in candidates if c.program.id != owner.program.id]
    if ":" in rule.with_:
        return [c for c in candidates if c.key == rule.with_ and c.key != owner.key]
    return [c for c in candidates if c.program.id == rule.with_ and c.key != owner.key]


def _warnings(fitting: list[FlatInstrument]) -> list[CombinationWarning]:
    """One warning per rule between fitting instruments, every instrument listed once.
    Rules against any other program (`with: "*"`) name only the owner's instruments, and
    those of the same type within one program are merged into one note."""
    warnings: list[CombinationWarning] = []
    for program in _unique_programs(f.program for f in fitting):
        owners = [f for f in fitting if f.program.id == program.id]
        general: dict[str, list[CombinationRule]] = {}
        for rule in program.combination_rules:
            if rule.type not in WARNING_TYPES:
                continue
            targets = {t.key: t for owner in owners for t in _targets(rule, owner, fitting)}
            if not targets:
                continue
            if rule.with_ == ANY_PROGRAM:
                general.setdefault(rule.type, []).append(rule)
            else:
                involved = {f.key: f for f in owners} | targets
                warnings.append(_warning(rule.type, list(involved.values()), [rule], owners[0]))
        warnings += [
            _warning(rule_type, owners, rules, owners[0]) for rule_type, rules in general.items()
        ]
    return warnings


def _warning(
    rule_type: str, items: list[FlatInstrument], rules: list[CombinationRule], owner: FlatInstrument
) -> CombinationWarning:
    source = rules[0].source
    return CombinationWarning(
        type=rule_type,
        items=list({f.key: f.ref for f in items}.values()),
        text=" ".join(rule.text for rule in rules),
        source=owner.source_link(source) if source else None,
    )


def _next_step(entry: TimelineEntry, item: FlatInstrument) -> NextStep:
    links = item.instrument.links
    return NextStep(
        text=entry.action,
        program_id=entry.program_id,
        instrument_id=entry.instrument_id,
        link=links.apply or links.info,
        due=entry.date,
    )


def _contact_programs(
    items: list[PlanItem], fitting: list[PlanItem], rejected: list[Rejected], kb: KnowledgeBase
) -> list[Program]:
    """Contacts of the fitting programs. If nothing fits, of the closest programs: those checked
    in detail first, then rejects by how far they got through the pre-filter (a later rule
    means more rules passed), cantonal offices first."""
    if fitting:
        return _unique_programs(p.item.program for p in fitting)
    rule_position = {rule: position for position, (rule, _) in enumerate(RULES)}
    closest_rejects = sorted(
        rejected,
        key=lambda r: (-rule_position[r.rule], _level_position(kb.get(r.program_id))),
    )
    looked_at = [p.item.program for p in items] + [
        program for r in closest_rejects if (program := kb.get(r.program_id))
    ]
    return _unique_programs(looked_at)[:CLOSEST_PROGRAMS]


def _level_position(program: Program | None) -> int:
    if program is None or program.level not in LEVEL_ORDER:
        return len(LEVEL_ORDER)
    return LEVEL_ORDER.index(program.level)


def _unique_programs(programs: Iterable[Program]) -> list[Program]:
    return list({p.id: p for p in programs}.values())


def _contacts(programs: list[Program]) -> list[FundingPlanContact]:
    contacts = [
        FundingPlanContact(name=c.name, role=c.role, email=c.email, phone=c.phone, url=c.url)
        for program in programs
        for c in program.contacts
        if c.name
    ]
    return list({c.name: c for c in contacts}.values())
