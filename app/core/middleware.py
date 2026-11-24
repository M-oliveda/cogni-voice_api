# SPDX-License-Identifier: GPL-2.0-or-later
"""Request middleware: request ID, access log, and last-resort error envelope.

A pure ASGI middleware (not ``BaseHTTPMiddleware``) so streaming responses and
``contextvars`` behave correctly (MASTERPLAN.md §19.6).
"""

import logging
import re
import time
import uuid
from typing import Final

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import unexpected_error_response
from app.core.request_context import request_id_var, route_var

REQUEST_ID_HEADER: Final = "x-request-id"
# Accepted client-supplied IDs: short and safe to echo in headers and logs.
_VALID_REQUEST_ID: Final = re.compile(r"[A-Za-z0-9._-]{1,128}")
# Probes are logged at DEBUG to keep log volume low (§19.2).
QUIET_PATHS: Final = frozenset({"/healthz", "/readyz"})

logger = logging.getLogger("app.access")


def resolve_request_id(header_value: str | None) -> str:
    """Reuse a valid client-supplied request ID or generate a new one.

    Args:
        header_value: The raw ``X-Request-ID`` header, if any.

    Returns:
        The request ID for this request.
    """
    if header_value and _VALID_REQUEST_ID.fullmatch(header_value):
        return header_value
    return str(uuid.uuid4())


class RequestContextMiddleware:
    """Bind the request ID, echo it, log the request, and catch crashes."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap an ASGI application.

        Args:
            app: The wrapped application.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle one ASGI connection.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive callable.
            send: The ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        raw_id = headers.get(REQUEST_ID_HEADER.encode())
        request_id = resolve_request_id(raw_id.decode("latin-1") if raw_id else None)
        id_token = request_id_var.set(request_id)
        route_token = route_var.set(scope["path"])
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                message["headers"] = [
                    *message.get("headers", []),
                    (REQUEST_ID_HEADER.encode(), request_id.encode()),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as error:  # pylint: disable=broad-exception-caught
            # Last resort: anything no exception handler claimed.
            if response_started:
                raise
            response = unexpected_error_response(error)
            await response(scope, receive, send_with_request_id)
        finally:
            self._log(scope, status_code, started)
            route_var.reset(route_token)
            request_id_var.reset(id_token)

    @staticmethod
    def _log(scope: Scope, status_code: int, started: float) -> None:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        level = logging.DEBUG if scope["path"] in QUIET_PATHS else logging.INFO
        logger.log(
            level,
            "%s %s %s",
            scope["method"],
            scope["path"],
            status_code,
            extra={
                "method": scope["method"],
                "status_code": status_code,
                "latency_ms": latency_ms,
            },
        )
