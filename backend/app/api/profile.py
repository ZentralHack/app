from fastapi import APIRouter

from app.agent.profile import extract_profile
from app.api.deps import LLMDep
from app.models.contract import ProfileRequest, ProfileResponse

router = APIRouter()


@router.post("/profile")
async def create_profile(req: ProfileRequest, llm: LLMDep) -> ProfileResponse:
    """Step 1: free text → profile, or one clarifying question if the text is too vague."""
    return await extract_profile(req, llm)
