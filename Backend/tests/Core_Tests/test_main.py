"""Tests for the real FastAPI application entrypoint."""

import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import Settings


class MainAppTests(unittest.TestCase):
    """Verify the production app module boots correctly."""

    def tearDown(self) -> None:
        sys.modules.pop("app.main", None)

    def test_main_module_exposes_health_endpoint(self) -> None:
        settings = Settings(
            _env_file=None,
            ai_api_key="test-key",
            enable_file_logging=False,
            prompt_base_path=Path("app/prompts"),
            mock_data_path=Path("app/mock_data"),
            log_file_path=Path("logs/app.log"),
        )

        with (
            patch("app.core.config.get_settings", return_value=settings),
            patch("app.core.logging.configure_logging") as configure_logging_mock,
            patch("app.core.connection.postgres_session"),
            patch("app.components.authorizer.seed.seed_rbac_defaults"),
            patch("app.utils.jwt._get_jwks"),
        ):
            sys.modules.pop("app.main", None)
            module = importlib.import_module("app.main")

            with TestClient(module.app) as client:
                response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Service is healthy")
        self.assertEqual(response.json()["data"]["service"], settings.app_name)
        self.assertEqual(module.app.title, settings.app_name)
        configure_logging_mock.assert_called_once_with(settings)
