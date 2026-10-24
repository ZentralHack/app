"""Step 0: load, validate and index the knowledge base once at startup."""

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
from pydantic import ValidationError

from app.knowledge_base.flat import FlatInstrument
from app.knowledge_base.questions import CriterionQuestion, build_question_index
from app.models.contract import InstrumentRef
from app.models.program import Program

log = logging.getLogger(__name__)

ANY_PROGRAM = "*"


@dataclass(frozen=True)
class InvalidFile:
    path: Path
    program_id: str
    name: str | None
    level: str | None
    errors: list[str]


@dataclass(frozen=True)
class KnowledgeBase:
    programs: list[Program]
    invalid: list[InvalidFile] = field(default_factory=list)
    questions: dict[str, CriterionQuestion] = field(default_factory=dict)

    def get(self, program_id: str) -> Program | None:
        return next((p for p in self.programs if p.id == program_id), None)

    def instruments(self) -> Iterator[FlatInstrument]:
        for program in self.programs:
            for instrument in program.instruments:
                yield FlatInstrument(program, instrument)

    def find(self, ref: InstrumentRef) -> FlatInstrument | None:
        program = self.get(ref.program_id)
        if program is None:
            return None
        instrument = next((i for i in program.instruments if i.id == ref.instrument_id), None)
        return FlatInstrument(program, instrument) if instrument else None

    def resolves(self, target: str) -> bool:
        """Whether a `combination_rules[].with` target exists."""
        if target == ANY_PROGRAM:
            return True
        program_id, _, instrument_id = target.partition(":")
        if not instrument_id:
            return self.get(program_id) is not None
        ref = InstrumentRef(program_id=program_id, instrument_id=instrument_id)
        return self.find(ref) is not None


def load_knowledge_base(directory: Path) -> KnowledgeBase:
    schema = json.loads((directory / "schema" / "program.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    programs: list[Program] = []
    invalid: list[InvalidFile] = []
    for path in sorted((directory / "programs").glob("*.json")):
        result = _load_program(path, validator)
        if isinstance(result, InvalidFile):
            log.error("Programmdatei übersprungen: %s: %s", path.name, "; ".join(result.errors))
            invalid.append(result)
        else:
            programs.append(result)
    kb = KnowledgeBase(programs, invalid, build_question_index(programs))
    for message in find_dead_references(kb):
        log.warning("Tote Referenz, wird ignoriert: %s", message)
    return kb


def _load_program(path: Path, validator: jsonschema.Draft202012Validator) -> Program | InvalidFile:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return InvalidFile(path, path.stem, None, None, [f"Kein gültiges JSON: {error}"])
    errors = [_format_error(e) for e in validator.iter_errors(data)]
    if not errors:
        try:
            program = Program.model_validate(data)
        except ValidationError as error:
            errors = [f"{'/'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()]
        else:
            errors = _consistency_errors(program, path)
            if not errors:
                return program
    meta = data if isinstance(data, dict) else {}
    return InvalidFile(
        path,
        str(meta.get("id") or path.stem),
        meta.get("name") if isinstance(meta.get("name"), str) else None,
        meta.get("level") if isinstance(meta.get("level"), str) else None,
        errors,
    )


def _format_error(error: jsonschema.ValidationError) -> str:
    location = "/".join(map(str, error.absolute_path)) or "(root)"
    return f"{location}: {error.message}"


def _consistency_errors(program: Program, path: Path) -> list[str]:
    errors = []
    if program.id != path.stem:
        errors.append(f"id '{program.id}' passt nicht zum Dateinamen '{path.stem}'")
    instrument_ids = [i.id for i in program.instruments]
    if len(instrument_ids) != len(set(instrument_ids)):
        errors.append("Instrument-IDs sind nicht eindeutig")
    return errors


def find_dead_references(kb: KnowledgeBase) -> list[str]:
    """References in `combination_rules[].with` and `levers[].affects_criteria` that
    point nowhere. They are ignored downstream."""
    dead = []
    for program in kb.programs:
        dead += [
            f"{program.id}: combination_rules[].with '{rule.with_}'"
            for rule in program.combination_rules
            if not kb.resolves(rule.with_)
        ]
        general_ids = {c.id for c in program.general_criteria}
        for instrument in program.instruments:
            known = general_ids | {c.id for c in instrument.criteria}
            dead += [
                f"{program.id}:{instrument.id}: levers[].affects_criteria '{criterion_id}'"
                for lever in instrument.levers
                for criterion_id in lever.affects_criteria
                if criterion_id not in known
            ]
    return dead
