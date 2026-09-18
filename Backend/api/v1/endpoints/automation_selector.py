"""Automation candidate selector API routes."""

from fastapi import APIRouter

from app.schemas.automation_selector import AutomationAnalysisData, AutomationAnalysisRequest
from app.schemas.common import SuccessResponse

router = APIRouter(tags=["Automation Selector"])


# Intentionally retained. Frontend currently calls Lambda directly due to API
# Gateway timeout constraints. This endpoint will be re-enabled when the request
# flow is moved back through the backend.
@router.post(
    "/automation-selector",
    response_model=SuccessResponse[AutomationAnalysisData],
    summary="Analyze test cases for automation suitability",
    # dependencies=[Depends(require_permission(Permission.AUTOMATION_ANALYZE))],
)
async def analyze_automation_candidates(
    payload: AutomationAnalysisRequest,
    # service: Annotated[AutomationSelectorService, Depends(get_automation_selector_service)],
) -> SuccessResponse[AutomationAnalysisData]:
    """Return automation recommendations for submitted test cases."""
    # analysis_result = await service.analyze(payload)
    return SuccessResponse(
        message="Automation analysis completed",
        data=[],
    )
