from fastapi import APIRouter

from app.agent.profile import extract_profile, with_form_fields
from app.api.deps import DemoDep, OptionalLLMDep, require_llm
from app.demo import profile_before_answers
from app.models.contract import ProfileRequest, ProfileResponse

router = APIRouter()


@router.post("/profile")
async def create_profile(
    req: ProfileRequest, llm: OptionalLLMDep, demo: DemoDep
) -> ProfileResponse:
    """Step 1: free text → profile, or one clarifying question if the text is too vague."""
    case = demo.find(req.text)
    if case is not None:
        # The form wins in the replay too, as in the live path.
        profile = with_form_fields(profile_before_answers(case.profile), req)
        return ProfileResponse(status="ok", profile=profile, clarification=None)
    return await extract_profile(req, require_llm(llm))
