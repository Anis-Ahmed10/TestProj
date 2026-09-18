"""Request ID and access logging middleware."""

import logging
import time
from collections.abc import MutableMapping
from typing import Any
from uuid import uuid4

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.utils.request_context import reset_request_id, set_request_id

logger = logging.getLogger(__name__)


class _RequestIdRegistry:
    """Small in-memory registry to detect repeated request IDs on one process."""

    def __init__(self, ttl_seconds: float = 300.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._seen: dict[str, float] = {}

    def is_duplicate(self, request_id: str) -> bool:
        """Return true when the request ID was seen recently."""
        now = time.monotonic()
        expired = [value for value, expires_at in self._seen.items() if expires_at <= now]
        for value in expired:
            self._seen.pop(value, None)
        duplicate = request_id in self._seen
        self._seen[request_id] = now + self.ttl_seconds
        return duplicate


class RequestContextMiddleware:
    """Attach a correlation ID and log request duration."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.registry = _RequestIdRegistry()

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Set request context for HTTP traffic."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        incoming_request_id = request.headers.get("X-Request-ID")
        request_id = incoming_request_id or str(uuid4())
        duplicate_request_id = bool(
            incoming_request_id and self.registry.is_duplicate(incoming_request_id)
        )
        if duplicate_request_id:
            request_id = str(uuid4())

        token = set_request_id(request_id)
        status_code = 500

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("utf-8")))
                if duplicate_request_id:
                    headers.append((b"x-duplicate-request-id", b"true"))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            reset_request_id(token)
