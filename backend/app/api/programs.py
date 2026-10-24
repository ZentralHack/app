from fastapi import APIRouter

from app.api.deps import KnowledgeBaseDep
from app.knowledge_base.loader import InvalidFile
from app.models.contract import ProgramSummary, ProgramSummaryInstrument
from app.models.program import Program

router = APIRouter()


@router.get("/programs")
def list_programs(kb: KnowledgeBaseDep) -> list[ProgramSummary]:
    """All program files, including invalid ones with their validation errors."""
    return [_valid_summary(p) for p in kb.programs] + [_invalid_summary(f) for f in kb.invalid]


def _valid_summary(program: Program) -> ProgramSummary:
    return ProgramSummary(
        id=program.id,
        name=program.name,
        level=program.level,
        valid=True,
        instruments=[ProgramSummaryInstrument(id=i.id, name=i.name) for i in program.instruments],
        last_verified=program.meta.last_verified,
        status=program.meta.status,
        errors=[],
    )


def _invalid_summary(file: InvalidFile) -> ProgramSummary:
    return ProgramSummary(
        id=file.program_id,
        name=file.name or file.path.name,
        level=file.level or "",
        valid=False,
        instruments=[],
        last_verified=None,
        status=None,
        errors=file.errors,
    )
