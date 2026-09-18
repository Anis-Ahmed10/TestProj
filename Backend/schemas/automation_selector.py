"""Schemas for automation candidate selection."""

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AutomationRecommendationValue(str, Enum):
    """Allowed automation recommendation values."""

    automate = "AUTOMATE"
    manual = "MANUAL"


class AutomationAnalysisRequest(BaseModel):
    """Request payload for automation suitability analysis."""

    test_cases: list[dict[str, Any]] = Field(..., min_length=1, max_length=200)

    @field_validator("test_cases")
    @classmethod
    def test_cases_must_be_json_objects(cls, values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Reject empty or non-serializable test case objects."""
        for item in values:
            if not item:
                raise ValueError("test_cases cannot contain empty objects")
            try:
                json.dumps(item, ensure_ascii=False)
            except TypeError as exc:
                raise ValueError("test_cases must be JSON serializable") from exc
        return values


class AutomationRecommendation(BaseModel):
    """Single automation recommendation."""

    model_config = ConfigDict(extra="allow")

    test_case_name: str = Field(..., min_length=1)
    recommendation: AutomationRecommendationValue
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: list[str] = Field(..., min_length=1)


class AutomationAnalysisData(BaseModel):
    """Automation analysis response data."""

    recommendations: list[AutomationRecommendation]
