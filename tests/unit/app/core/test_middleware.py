# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the request-context middleware."""

import logging
import uuid

import pytest
from fastapi import FastAPI
from starlette.types import Message, Receive, Scope, Send

from app.core.middleware import RequestContextMiddleware, resolve_request_id
from app.core.request_context import get_request_id
from app.main import create_app
from tests.conftest import make_settings, running_app


@pytest.mark.parametrize("value", ["abc-123", "A.b_C-9", "x" * 128])
def test_valid_client_request_ids_are_kept(value: str) -> None:
    assert resolve_request_id(value) == value


@pytest.mark.parametrize("value", [None, "", "x" * 129, "has space", "bad\nline"])
def test_invalid_request_ids_are_replaced(value: str | None) -> None:
    assert uuid.UUID(resolve_request_id(value)).version == 4


def _app() -> FastAPI:
    app = create_app(make_settings())

    @app.get("/whoami")
    async def whoami() -> dict[str, str | None]:
        return {"request_id": get_request_id()}

    return app


async def test_request_id_is_bound_and_echoed() -> None:
    async with running_app(_app()) as client:
        response = await client.get("/whoami", headers={"X-Request-ID": "req-42"})

    assert response.json() == {"request_id": "req-42"}
    assert response.headers["x-request-id"] == "req-42"
    assert get_request_id() is None


async def test_generated_request_id_is_returned() -> None:
    async with running_app(_app()) as client:
        response = await client.get("/whoami")

    assert response.json()["request_id"] == response.headers["x-request-id"]


async def test_requests_are_logged_with_status_and_latency(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="app.access")
    async with running_app(_app()) as client:
        await client.get("/whoami")
        await client.get("/healthz")

    whoami, health = [r for r in caplog.records if r.name == "app.access"]
    fields = vars(whoami)
    assert whoami.levelno == logging.INFO
    assert (fields["status_code"], fields["method"]) == (200, "GET")
    assert fields["latency_ms"] >= 0
    assert health.levelno == logging.DEBUG


async def test_errors_after_the_response_started_are_reraised() -> None:
    sent: list[Message] = []

    async def streaming_crash(scope: Scope, receive: Receive, send: Send) -> None:
        del scope, receive
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("mid-stream")

    async def record(message: Message) -> None:
        sent.append(message)

    middleware = RequestContextMiddleware(streaming_crash)
    scope: Scope = {"type": "http", "method": "GET", "path": "/s", "headers": []}
    with pytest.raises(RuntimeError, match="mid-stream"):
        await middleware(scope, _no_body, record)

    assert len(sent) == 1
    assert (b"x-request-id", sent[0]["headers"][0][1]) == sent[0]["headers"][0]


async def _no_body() -> Message:
    return {"type": "http.request", "body": b""}


async def test_non_http_scopes_pass_through() -> None:
    seen: list[str] = []

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        del receive, send
        seen.append(str(scope["type"]))

    async def ignore(message: Message) -> None:
        del message

    middleware = RequestContextMiddleware(inner)
    await middleware({"type": "lifespan"}, _no_body, ignore)

    assert seen == ["lifespan"]
