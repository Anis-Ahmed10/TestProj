"""Tests for request body size limiting middleware."""

import asyncio
import unittest

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.body_size import BodySizeLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware


class BodySizeLimitMiddlewareTests(unittest.TestCase):
    """Verify payload-size guard behavior."""

    def setUp(self) -> None:
        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=32)
        app.add_middleware(RequestContextMiddleware)

        @app.post("/echo")
        async def echo(request: Request) -> dict[str, str]:
            return {"body": (await request.body()).decode("utf-8")}

        self.client = TestClient(app)

    def test_allows_request_with_small_body(self) -> None:
        response = self.client.post("/echo", content="small body")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"body": "small body"})

    def test_rejects_request_when_content_length_exceeds_limit(self) -> None:
        response = self.client.post("/echo", content="x" * 64)

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"], "PAYLOAD_TOO_LARGE")
        self.assertTrue(response.headers["x-request-id"])

    def test_invalid_content_length_is_treated_as_too_large(self) -> None:
        middleware = BodySizeLimitMiddleware(lambda scope, receive, send: None, max_body_size=32)

        self.assertTrue(middleware._content_length_exceeds_limit("abc"))

    def test_non_http_scope_is_passed_through(self) -> None:
        calls: list[str] = []

        async def app(scope, receive, send) -> None:
            calls.append(scope["type"])

        middleware = BodySizeLimitMiddleware(app, max_body_size=32)

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

    def test_streaming_body_over_limit_returns_payload_too_large(self) -> None:
        sent_messages = []

        async def app(scope, receive, send) -> None:
            await receive()
            await receive()

        middleware = BodySizeLimitMiddleware(app, max_body_size=3)
        messages = iter(
            [
                {"type": "http.request", "body": b"ab", "more_body": True},
                {"type": "http.request", "body": b"cd", "more_body": False},
            ]
        )

        async def receive():
            return next(messages)

        async def send(message) -> None:
            sent_messages.append(message)

        asyncio.run(
            middleware(
                {"type": "http", "method": "POST", "path": "/echo", "headers": []},
                receive,
                send,
            )
        )

        self.assertEqual(sent_messages[0]["status"], 413)

    def test_non_bytes_request_body_is_ignored_for_length_count(self) -> None:
        calls = []

        async def app(scope, receive, send) -> None:
            calls.append(await receive())

        middleware = BodySizeLimitMiddleware(app, max_body_size=3)

        async def receive():
            return {"type": "http.request", "body": "abcd", "more_body": False}

        async def send(message) -> None:
            return None

        asyncio.run(
            middleware(
                {"type": "http", "method": "POST", "path": "/echo", "headers": []},
                receive,
                send,
            )
        )

        self.assertEqual(calls[0]["body"], "abcd")

    def test_non_request_message_passes_through_receive_wrapper(self) -> None:
        calls = []

        async def app(scope, receive, send) -> None:
            calls.append(await receive())

        middleware = BodySizeLimitMiddleware(app, max_body_size=3)

        async def receive():
            return {"type": "http.disconnect"}

        async def send(message) -> None:
            return None

        asyncio.run(
            middleware(
                {"type": "http", "method": "POST", "path": "/echo", "headers": []},
                receive,
                send,
            )
        )

        self.assertEqual(calls[0]["type"], "http.disconnect")
