"""An instrument together with the program data it inherits."""

from dataclasses import dataclass
from typing import Literal

from app.knowledge_base.partners import partner_criteria
from app.knowledge_base.purpose import purpose_criterion
from app.models.contract import InstrumentRef, SourceLink
from app.models.program import Criterion, Instrument, Lever, Program, SourceRef

CriterionScope = Literal["programm", "instrument", "filter"]


@dataclass(frozen=True)
class ScopedCriterion:
    scope: CriterionScope
    criterion: Criterion


@dataclass(frozen=True)
class FlatInstrument:
    """Matching runs per instrument. Program-wide criteria, scope, entitlement,
    combination rules and sources are reached through `program`."""

    program: Program
    instrument: Instrument

    @property
    def ref(self) -> InstrumentRef:
        return InstrumentRef(program_id=self.program.id, instrument_id=self.instrument.id)

    @property
    def key(self) -> str:
        return f"{self.program.id}:{self.instrument.id}"

    def criteria(self) -> list[ScopedCriterion]:
        """The generated purpose criterion, program-wide criteria, the instrument's own, then
        generated partner criteria."""
        return (
            [ScopedCriterion("instrument", purpose_criterion(self.program, self.instrument))]
            + [ScopedCriterion("programm", c) for c in self.program.general_criteria]
            + [ScopedCriterion("instrument", c) for c in self.instrument.criteria]
            + [ScopedCriterion("filter", c) for c in partner_criteria(self.instrument)]
        )

    def levers_for(self, criterion_id: str) -> list[Lever]:
        return [lever for lever in self.instrument.levers if criterion_id in lever.affects_criteria]

    def source_link(self, ref: SourceRef | None) -> SourceLink | None:
        """Resolve a source reference; falls back to the instrument's own source."""
        ref = ref or self.instrument.source
        source = self.program.source(ref)
        if ref is None or source is None:
            return None
        return SourceLink(title=source.title, url=source.url, locator=ref.locator)

    def criterion_source(self, ref: SourceRef | None) -> SourceLink:
        """Like `source_link`, but never empty: falls back to the program's first source."""
        link = self.source_link(ref)
        if link is not None:
            return link
        first = self.program.sources[0]
        return SourceLink(title=first.title, url=first.url, locator=None)
