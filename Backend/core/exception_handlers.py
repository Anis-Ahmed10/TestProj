"""FastAPI exception handlers that return the standard error shape."""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException
from app.schemas.common import ErrorDetail, ErrorResponse
from app.utils.request_context import get_request_id

logger = logging.getLogger(__name__)


def _error_response(code: str, message: str, status_code: int) -> JSONResponse:
    payload = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
        headers={"X-Request-ID": get_request_id()},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register safe error handlers for expected and unexpected failures."""

    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            "application_error",
            extra={"error_code": exc.code, "status_code": exc.status_code},
        )
        return _error_response(exc.code, exc.message, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        error_types = {str(error.get("type")) for error in exc.errors()}
        code = "INVALID_JSON" if "json_invalid" in error_types else "INVALID_INPUT"
        message = (
            "Request body must be valid JSON"
            if code == "INVALID_JSON"
            else "Request validation failed"
        )
        logger.warning(
            "request_validation_error",
            extra={"error_code": code, "validation_error_count": len(exc.errors())},
        )
        return _error_response(code, message, HTTPStatus.UNPROCESSABLE_ENTITY)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        status_code = int(exc.status_code)
        code = "NOT_FOUND" if status_code == HTTPStatus.NOT_FOUND else "HTTP_ERROR"
        if code == "NOT_FOUND":
            message = "Resource not found"
        else:
            message = str(exc.detail) if exc.detail else "Request failed"
        logger.warning(
            "http_error",
            extra={"error_code": code, "status_code": status_code},
        )
        return _error_response(code, message, status_code)

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unexpected_error",
            extra={"error_code": "INTERNAL_SERVER_ERROR"},
        )
        return _error_response(
            "INTERNAL_SERVER_ERROR",
            "An unexpected error occurred",
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
