"""Structured JSON logging with correlation ID and secret redaction."""

import json
import logging
import re
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Context variables for tracing across async execution flows
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")
job_id_ctx: ContextVar[str] = ContextVar("job_id", default="")

# Regex patterns detecting sensitive credentials and secrets
BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+([a-zA-Z0-9_\-\.]+)")
SECRET_KEY_PATTERN = re.compile(
    r"(?i)\b(token|secret|password|authorization|api[-_]?key)\s*[:=]\s*([\"\']?[a-zA-Z0-9_\-\.]{4,}[\"\']?)",
    re.IGNORECASE,
)


class SecretRedactionFilter(logging.Filter):
    """Redacts sensitive credentials from log records before emission."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: (self._redact(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    (self._redact(arg) if isinstance(arg, str) else arg) for arg in record.args
                )
        return True

    @classmethod
    def _redact(cls, text: str) -> str:
        # Redact Bearer tokens
        text = BEARER_PATTERN.sub("Bearer [REDACTED]", text)

        # Redact key-value secrets
        def replace_kv(m: re.Match) -> str:
            key = m.group(1)
            return f"{key}=[REDACTED]"

        text = SECRET_KEY_PATTERN.sub(replace_kv, text)
        return text


class JSONFormatter(logging.Formatter):
    """Outputs single-line JSON log entries."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach correlation ID and job ID if present in async context or extra
        corr_id = getattr(record, "correlation_id", None) or correlation_id_ctx.get()
        if corr_id:
            log_obj["correlation_id"] = corr_id

        j_id = getattr(record, "job_id", None) or job_id_ctx.get()
        if j_id:
            log_obj["job_id"] = j_id

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logging(level_name: str = "INFO") -> None:
    """Configures the root logger with the JSON formatter and redaction filter."""
    root = logging.getLogger()
    root.setLevel(level_name.upper())

    # Avoid duplicate handlers on re-initialization
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SecretRedactionFilter())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Returns a logger instance configured with the redaction filter."""
    logger = logging.getLogger(name)
    return logger
