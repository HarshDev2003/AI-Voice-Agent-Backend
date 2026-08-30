"""Structured JSON logging for the MVP.

Provides a small stdlib-based JSON formatter and a ``setup_logging`` helper so
the app logs machine-readable, JSON lines to stdout with optional call context.
"""
import json
import logging
import sys
from datetime import UTC, datetime

from app.core.config import get_settings


class JsonFormatter(logging.Formatter):
    """Format log records as a single JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        call_sid = getattr(record, "call_sid", None)
        if call_sid is not None:
            payload["call_sid"] = call_sid
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    """Configure the root logger to emit structured JSON to stdout."""
    settings = get_settings()
    root = logging.getLogger()
    if any(isinstance(handler.formatter, JsonFormatter) for handler in root.handlers):
        return  # already configured
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL.upper())