"""Test case generator API routes."""

import logging

from fastapi import APIRouter

from app.core.exceptions import AppException
from app.schemas.common import SuccessResponse
from app.schemas.test_case_generator import TestCaseGenerationData, TestCaseGenerationRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Test Case Generator"])

# Intentionally retained. Frontend currently calls Lambda directly due to API
# Gateway timeout constraints. This endpoint will be re-enabled when the request
# flow is moved back through the backend.


@router.post(
    "/test-generator",
    response_model=SuccessResponse[TestCaseGenerationData],
    response_model_exclude_none=True,
    summary="Generate AI-assisted test cases",
    # dependencies=[Depends(require_permission(Permission.TEST_CASE_GENERATION))],
)
async def generate_test_cases(
    payload: TestCaseGenerationRequest,
    # service: Annotated[TestCaseGeneratorService, Depends(get_test_case_generator_service)],
) -> SuccessResponse[TestCaseGenerationData]:
    """Generate structured, UI-friendly test cases from a user story."""
    try:
        # test_case_generation_data = await service.generate_test_cases(payload)
        test_case_generation_data = []
    except AppException:  # pragma: no cover - re-enabled with the real service flow
        raise
    except Exception:  # pragma: no cover - re-enabled with the real service flow
        logger.exception("test_case_generation_failed")
        raise

    # if test_case_generation_data.generation_issues:
    #     message = "Test cases generated with partial failures"

    return SuccessResponse(
        message="Test cases generated successfully",
        data=test_case_generation_data,
    )
