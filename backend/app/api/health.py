from fastapi import APIRouter

from app.api.deps import KnowledgeBaseDep, SettingsDep
from app.knowledge_base.catalog_loader import QuestionCatalog
from app.models.contract import Health, HealthQuestionCatalog

router = APIRouter()


@router.get("/health")
def health(settings: SettingsDep, kb: KnowledgeBaseDep) -> Health:
    catalog = _catalog_status(kb.catalog)
    healthy = (
        settings.llm_configured and bool(kb.programs) and not kb.invalid and not catalog.errors
    )
    return Health(
        status="ok" if healthy else "eingeschraenkt",
        llm_available=settings.llm_configured,
        programs_loaded=len(kb.programs),
        programs_invalid=len(kb.invalid),
        question_catalog=catalog,
    )


def _catalog_status(catalog: QuestionCatalog) -> HealthQuestionCatalog:
    counts = catalog.review_counts()
    errors = [catalog.error] if catalog.error else []
    errors += [f"{f.field}: {f.message}" for f in catalog.findings if f.severity == "fehler"]
    return HealthQuestionCatalog(
        entries=len(catalog.entries),
        verified=counts["verified"],
        needs_review=counts["needs_review"],
        draft=counts["draft"],
        veraltet=counts["veraltet"],
        errors=errors,
    )
