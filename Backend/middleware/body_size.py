"""Request body size limiting middleware."""

from http import HTTPStatus

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.schemas.common import ErrorDetail, ErrorResponse
from app.utils.request_context import get_request_id


class PayloadTooLargeError(Exception):
    """Raised when a streaming request body exceeds the configured limit."""


class BodySizeLimitMiddleware:
    """Reject request bodies that exceed the configured byte limit."""

    def __init__(self, app: ASGIApp, max_body_size: int) -> None:
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Apply the body-size limit to HTTP requests."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        content_length = request.headers.get("content-length")
        if content_length and self._content_length_exceeds_limit(content_length):
            response = self._too_large_response()
            await response(scope, receive, send)
            return

        received_bytes = 0

        async def limited_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if isinstance(body, bytes):
                    received_bytes += len(body)
                if received_bytes > self.max_body_size:
                    raise PayloadTooLargeError()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except PayloadTooLargeError:
            response = self._too_large_response()
            await response(scope, receive, send)

    def _content_length_exceeds_limit(self, content_length: str) -> bool:
        try:
            return int(content_length) > self.max_body_size
        except ValueError:
            return True

    def _too_large_response(self) -> JSONResponse:
        payload = ErrorResponse(
            error=ErrorDetail(
                code="PAYLOAD_TOO_LARGE",
                message="Request payload exceeds the configured size limit",
            )
        )
        return JSONResponse(
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            content=payload.model_dump(),
            headers={"X-Request-ID": get_request_id()},
        )
