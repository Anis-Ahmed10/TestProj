"""Tests for API exception handlers."""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.exception_handlers import register_exception_handlers
from app.core.exceptions import InvalidInputError
from app.middleware.request_context import RequestContextMiddleware


class _Payload(BaseModel):
    """Simple request payload for validation tests."""

    value: int


class ExceptionHandlerTests(unittest.TestCase):
    """Verify error responses use the standard API shape."""

    def setUp(self) -> None:
        app = FastAPI()
        app.add_middleware(RequestContextMiddleware)
        register_exception_handlers(app)

        @app.get("/app-error")
        async def app_error() -> None:
            raise InvalidInputError("Bad input")

        @app.post("/validate")
        async def validate(payload: _Payload) -> dict[str, int]:
            return {"value": payload.value}

        @app.get("/explode")
        async def explode() -> None:
            raise RuntimeError("boom")

        self.client = TestClient(app, raise_server_exceptions=False)

    def test_handles_app_exception(self) -> None:
        response = self.client.get("/app-error")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_INPUT")
        self.assertEqual(response.json()["error"]["message"], "Bad input")
        self.assertTrue(response.headers["x-request-id"])

    def test_handles_invalid_json_body(self) -> None:
        response = self.client.post(
            "/validate",
            content="{not-json}",
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_JSON")

    def test_handles_request_validation_errors(self) -> None:
        response = self.client.post("/validate", json={"value": "wrong"})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_INPUT")
        self.assertEqual(response.json()["error"]["message"], "Request validation failed")

    def test_handles_not_found(self) -> None:
        response = self.client.get("/missing")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_handles_unexpected_exceptions(self) -> None:
        response = self.client.get("/explode")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "INTERNAL_SERVER_ERROR")
