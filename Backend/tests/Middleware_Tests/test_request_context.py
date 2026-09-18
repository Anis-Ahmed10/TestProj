"""Tests for request ID utilities and middleware."""

import asyncio
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.request_context import RequestContextMiddleware, _RequestIdRegistry
from app.utils.request_context import get_request_id, reset_request_id, set_request_id


class RequestContextUtilityTests(unittest.TestCase):
    """Verify context-local request ID helpers."""

    def test_set_get_and_reset_request_id(self) -> None:
        token = set_request_id("req-123")
        try:
            self.assertEqual(get_request_id(), "req-123")
        finally:
            reset_request_id(token)

        self.assertEqual(get_request_id(), "")


class RequestIdRegistryTests(unittest.TestCase):
    """Verify duplicate detection logic."""

    def test_duplicate_detection_expires_after_ttl(self) -> None:
        registry = _RequestIdRegistry(ttl_seconds=0.0)

        first_duplicate = registry.is_duplicate("req-1")
        second_duplicate = registry.is_duplicate("req-1")

        self.assertFalse(first_duplicate)
        self.assertFalse(second_duplicate)


class RequestContextMiddlewareTests(unittest.TestCase):
    """Verify HTTP request context behavior."""

    def setUp(self) -> None:
        app = FastAPI()
        app.add_middleware(RequestContextMiddleware)

        @app.get("/ping")
        async def ping() -> dict[str, str]:
            return {"request_id": get_request_id()}

        self.client = TestClient(app)

    def test_generates_request_id_when_header_is_missing(self) -> None:
        response = self.client.get("/ping")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["x-request-id"])
        self.assertEqual(response.json()["request_id"], response.headers["x-request-id"])

    def test_reuses_incoming_request_id_once_then_marks_duplicate(self) -> None:
        first = self.client.get("/ping", headers={"X-Request-ID": "same-id"})
        second = self.client.get("/ping", headers={"X-Request-ID": "same-id"})

        self.assertEqual(first.headers["x-request-id"], "same-id")
        self.assertEqual(first.json()["request_id"], "same-id")
        self.assertEqual(second.headers["x-duplicate-request-id"], "true")
        self.assertNotEqual(second.headers["x-request-id"], "same-id")

    def test_non_http_scope_is_passed_through(self) -> None:
        calls: list[str] = []

        async def app(scope, receive, send) -> None:
            calls.append(scope["type"])

        middleware = RequestContextMiddleware(app)

        async def receive():
            return {"type": "websocket.disconnect"}

        async def send(message) -> None:
            return None

        asyncio.run(
            middleware(
                {"type": "websocket", "headers": [], "path": "/ws"},
                receive,
                send,
            )
        )

        self.assertEqual(calls, ["websocket"])
