"""Tests for structured logging helpers."""

import io
import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import Settings
from app.core.logging import JsonLogFormatter, configure_logging
from app.utils.request_context import reset_request_id, set_request_id


class JsonLogFormatterTests(unittest.TestCase):
    """Verify JSON log formatting behavior."""

    def test_formats_log_record_with_request_id_and_extra_fields(self) -> None:
        token = set_request_id("req-789")
        try:
            record = logging.getLogger("tests").makeRecord(
                name="tests.logger",
                level=logging.INFO,
                fn=__file__,
                lno=10,
                msg="hello %s",
                args=("world",),
                exc_info=None,
                extra={"user_id": 7},
            )
            payload = json.loads(JsonLogFormatter().format(record))
        finally:
            reset_request_id(token)

        self.assertEqual(payload["message"], "hello world")
        self.assertEqual(payload["request_id"], "req-789")
        self.assertEqual(payload["user_id"], 7)
        self.assertNotIn("args", payload)

    def test_formats_exception_when_exc_info_is_present(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            record = logging.getLogger("tests").makeRecord(
                name="tests.logger",
                level=logging.ERROR,
                fn=__file__,
                lno=20,
                msg="failed",
                args=(),
                exc_info=sys.exc_info(),
            )

        payload = json.loads(JsonLogFormatter().format(record))

        self.assertIn("exception", payload)
        self.assertIn("ValueError: boom", payload["exception"])


class ConfigureLoggingTests(unittest.TestCase):
    """Verify root logging configuration."""

    def setUp(self) -> None:
        Path(".temp").mkdir(exist_ok=True)
        self.root_logger = logging.getLogger()
        self.original_handlers = list(self.root_logger.handlers)
        self.original_level = self.root_logger.level
        self.temp_dir = tempfile.TemporaryDirectory(dir=".temp")

    def tearDown(self) -> None:
        current_handlers = list(self.root_logger.handlers)
        self.root_logger.handlers.clear()
        for handler in current_handlers:
            if handler not in self.original_handlers:
                handler.close()
        for handler in self.original_handlers:
            self.root_logger.addHandler(handler)
        self.root_logger.setLevel(self.original_level)
        self.temp_dir.cleanup()

    def test_configure_logging_adds_console_and_file_handlers(self) -> None:
        log_file_path = Path(self.temp_dir.name) / "logs" / "app.log"
        settings = Settings(
            _env_file=None,
            ai_api_key="test-key",
            enable_file_logging=True,
            log_file_path=log_file_path,
            prompt_base_path=Path("app/prompts"),
            mock_data_path=Path("app/mock_data"),
        )

        with patch("app.core.logging.sys.stdout", new=io.StringIO()):
            configure_logging(settings)
            logging.getLogger("tests").info("written to file")
            for handler in self.root_logger.handlers:
                handler.flush()

        self.assertEqual(len(self.root_logger.handlers), 2)
        self.assertTrue(log_file_path.exists())
        self.assertIn("written to file", log_file_path.read_text(encoding="utf-8"))

    def test_configure_logging_without_file_handler_only_adds_console(self) -> None:
        settings = Settings(
            _env_file=None,
            ai_api_key="test-key",
            enable_file_logging=False,
            prompt_base_path=Path("app/prompts"),
            mock_data_path=Path("app/mock_data"),
            log_file_path=Path(self.temp_dir.name) / "app.log",
        )

        configure_logging(settings)

        self.assertEqual(len(self.root_logger.handlers), 1)
