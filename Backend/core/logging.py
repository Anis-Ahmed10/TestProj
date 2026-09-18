"""Structured logging configuration."""

import json
import logging
import sys
import time
from logging import LogRecord

from app.core.config import Settings
from app.utils.request_context import get_request_id


class JsonLogFormatter(logging.Formatter):
    """Render log records as compact JSON objects."""

    def format(self, record: LogRecord) -> str:
        """Format a log record without including sensitive request payloads."""
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _RESERVED_LOG_RECORD_KEYS:
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


_RESERVED_LOG_RECORD_KEYS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


def configure_logging(settings: Settings) -> None:
    """Configure console and optional file logging."""
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(settings.log_level)

    formatter = JsonLogFormatter()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(settings.log_level)
    root_logger.addHandler(console_handler)

    if settings.enable_file_logging:
        settings.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(settings.log_file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(settings.log_level)
        root_logger.addHandler(file_handler)


# Configure default application logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
