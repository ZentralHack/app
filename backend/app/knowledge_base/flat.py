"""An instrument together with the program data it inherits."""

from dataclasses import dataclass
from typing import Literal

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
        """Program-wide criteria first, then the instrument's own."""
        return [ScopedCriterion("programm", c) for c in self.program.general_criteria] + [
            ScopedCriterion("instrument", c) for c in self.instrument.criteria
        ]

    def levers_for(self, criterion_id: str) -> list[Lever]:
        return [lever for lever in self.instrument.levers if criterion_id in lever.affects_criteria]

    def source_link(self, ref: SourceRef | None) -> SourceLink | None:
        """Resolve a source reference; falls back to the instrument's own source."""
        ref = ref or self.instrument.source
        source = self.program.source(ref)
        if ref is None or source is None:
            return None
        return SourceLink(title=source.title, url=source.url, locator=ref.locator)
