"""Common API response schemas."""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

DataT = TypeVar("DataT")


class HealthData(BaseModel):
    """Health check response data."""

    status: str
    service: str


class SuccessResponse(BaseModel, Generic[DataT]):
    """Standard success response wrapper."""

    success: Literal[True] = True
    message: str
    data: DataT


class ErrorDetail(BaseModel):
    """Standard error detail."""

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error response wrapper."""

    success: Literal[False] = False
    error: ErrorDetail


class FlexibleModel(BaseModel):
    """Base model that allows provider-specific or AI-generated fields."""

    model_config = ConfigDict(extra="allow")
