from fastapi import APIRouter

from app.agent.normalize import validate_profile
from app.agent.questions import build_questions
from app.api.deps import KnowledgeBaseDep
from app.models.contract import QuestionSet, QuestionsRequest

router = APIRouter()


@router.post("/questions")
def questions(req: QuestionsRequest, kb: KnowledgeBaseDep) -> QuestionSet:
    """Pre-filter and question selection, pure code. Empty set: skip Screen 3."""
    validate_profile(req.profile, kb.criterion_questions)
    return build_questions(req.profile, kb)
