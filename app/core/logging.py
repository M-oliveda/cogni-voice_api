# SPDX-License-Identifier: GPL-2.0-or-later
"""Structured JSON logging on stdout (MASTERPLAN.md §19.2).

Every line carries ``timestamp``, ``severity``, ``message``, ``request_id``,
``app_env``, ``tenant_id``, ``route``, ``status_code`` and ``latency_ms`` (the
last ones when known). ``local`` uses a human-readable renderer instead.

Logs must never contain interaction text, prompts, agent questions or answers,
API keys, JWTs, connection strings or secrets. Callers must not log them; the
:class:`RedactionFilter` is the second line of defence.
"""

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any, Final

from app.core.config import AppEnv, Settings
from app.core.request_context import request_id_var, route_var, tenant_id_var

REDACTED: Final = "[REDACTED]"

# ``extra`` fields that may hold user content; they are dropped entirely.
SENSITIVE_FIELDS: Final = frozenset(
    {
        "text",
        "text_content",
        "prompt",
        "prompts",
        "question",
        "answer",
        "password",
        "secret",
        "token",
        "api_key",
        "authorization",
        "database_url",
        "database_migration_url",
    }
)

# Optional structured fields copied from ``extra`` when present.
CONTEXT_FIELDS: Final = (
    "status_code",
    "latency_ms",
    "method",
    "error_code",
    "interaction_id",
    "task_name",
    "attempt",
    "outcome",
)

_SECRET_PATTERNS: Final = (
    # JWTs: three base64url segments, the first starting with ``eyJ``.
    re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+"),
    # CogniVoice API keys (MASTERPLAN.md §5).
    re.compile(r"cvk_\w+"),
    # Authorization header values.
    re.compile(r"(?i)\bbearer\s+[\w.~+/=-]+"),
)
# Password part of a connection string: scheme://user:PASSWORD@host
_URL_PASSWORD: Final = re.compile(r"(\w+://[^:/@\s]+:)[^@\s]+(@)")

# Attributes every LogRecord has; anything else came from ``extra``.
_RECORD_ATTRIBUTES: Final = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", None, None))
) | {"message", "asctime", "taskName"}


def redact(text: str) -> str:
    """Mask secrets that match known patterns.

    Args:
        text: Any text about to be logged.

    Returns:
        The text with JWTs, API keys, bearer tokens and connection-string
        passwords replaced by ``[REDACTED]``.
    """
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(REDACTED, text)
    return _URL_PASSWORD.sub(rf"\g<1>{REDACTED}\g<2>", text)


class RedactionFilter(logging.Filter):
    """Drop sensitive ``extra`` fields and mask secrets in the message."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Sanitise the record in place; never suppress it.

        Args:
            record: The record being logged.

        Returns:
            Always ``True``.
        """
        for name in SENSITIVE_FIELDS & vars(record).keys():
            delattr(record, name)
        record.msg = redact(record.getMessage())
        record.args = None
        if record.exc_info:
            record.exc_text = redact(
                logging.Formatter().formatException(record.exc_info)
            )
            record.exc_info = None
        return True


class JsonFormatter(logging.Formatter):
    """Render each record as one JSON object."""

    def __init__(self, app_env: str) -> None:
        """Create the formatter.

        Args:
            app_env: Value of the ``app_env`` field on every line.
        """
        super().__init__()
        self._app_env = app_env

    def format(self, record: logging.LogRecord) -> str:
        """Return the JSON line for one record.

        Args:
            record: The record to render.

        Returns:
            A single-line JSON document.
        """
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "app_env": self._app_env,
            "request_id": request_id_var.get(),
            "tenant_id": tenant_id_var.get(),
            "route": route_var.get(),
        }
        for name in CONTEXT_FIELDS:
            if name in vars(record):
                payload[name] = getattr(record, name)
        if record.exc_text:
            payload["exception"] = record.exc_text
        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable lines for ``local`` development."""

    def format(self, record: logging.LogRecord) -> str:
        """Return a readable line for one record.

        Args:
            record: The record to render.

        Returns:
            ``time LEVEL [request_id] logger: message key=value...``.
        """
        extras = " ".join(
            f"{name}={getattr(record, name)}"
            for name in CONTEXT_FIELDS
            if name in vars(record)
        )
        line = (
            f"{self.formatTime(record)} {record.levelname:<7} "
            f"[{request_id_var.get() or '-'}] {record.name}: {record.getMessage()}"
        )
        if extras:
            line = f"{line} {extras}"
        if record.exc_text:
            line = f"{line}\n{record.exc_text}"
        return line


class StdoutHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """The handler installed by :func:`configure_logging`."""


def configure_logging(settings: Settings) -> None:
    """Send every log record to stdout through the redaction filter.

    Replaces the handler installed by a previous call (other handlers, such as
    pytest's, are kept), so it is safe to call more than once. Uvicorn's own
    loggers propagate to the root logger.

    Args:
        settings: The application settings.
    """
    handler = StdoutHandler(sys.stdout)
    handler.addFilter(RedactionFilter())
    if settings.app_env is AppEnv.LOCAL:
        handler.setFormatter(ConsoleFormatter())
    else:
        handler.setFormatter(JsonFormatter(settings.app_env.value))
    root = logging.getLogger()
    root.handlers = [
        *(item for item in root.handlers if not isinstance(item, StdoutHandler)),
        handler,
    ]
    root.setLevel(settings.log_level.value)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    # The request middleware writes its own access line with latency.
    logging.getLogger("uvicorn.access").disabled = True
