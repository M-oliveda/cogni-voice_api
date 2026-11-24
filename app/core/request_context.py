# SPDX-License-Identifier: GPL-2.0-or-later
"""Per-request context shared with the logger (MASTERPLAN.md §19.6).

Values live in ``contextvars`` so every log line written while a request is
handled carries its ``request_id`` (and later its ``tenant_id``) without passing
them around explicitly.
"""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)
route_var: ContextVar[str | None] = ContextVar("route", default=None)


def get_request_id() -> str | None:
    """Return the ID of the request being handled, if any.

    Returns:
        The request ID, or ``None`` outside a request.
    """
    return request_id_var.get()
