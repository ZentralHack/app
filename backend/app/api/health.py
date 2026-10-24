from fastapi import APIRouter

from app.api.deps import KnowledgeBaseDep, SettingsDep
from app.models.contract import Health

router = APIRouter()


@router.get("/health")
def health(settings: SettingsDep, kb: KnowledgeBaseDep) -> Health:
    healthy = settings.llm_configured and bool(kb.programs) and not kb.invalid
    return Health(
        status="ok" if healthy else "eingeschraenkt",
        llm_available=settings.llm_configured,
        programs_loaded=len(kb.programs),
        programs_invalid=len(kb.invalid),
    )
