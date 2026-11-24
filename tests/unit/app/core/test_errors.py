# SPDX-License-Identifier: GPL-2.0-or-later
"""Every failure is returned as the error envelope."""

# Fixtures that depend on other fixtures take them as same-named parameters.
# pylint: disable=redefined-outer-name

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from app.core.errors import (
    AIProviderError,
    AppError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from app.main import create_app
from tests.conftest import make_settings, running_app


class Payload(BaseModel):
    name: str
    count: int


def _build_app() -> FastAPI:
    app = create_app(make_settings())

    @app.get("/fail/{kind}")
    async def fail(kind: str) -> None:
        errors: dict[str, Exception] = {
            "conflict": ConflictError(details={"field": "slug"}),
            "custom": NotFoundError("Tenant not found."),
            "ai": AIProviderError(),
            "operational": OperationalError("SELECT 1", {}, Exception("down")),
            "pool": PoolTimeoutError(),
            "teapot": HTTPException(status_code=418),
            "http-detail": HTTPException(status_code=401, detail="Bad token."),
            "crash": ValueError("customer text must never be echoed"),
        }
        raise errors[kind]

    @app.post("/echo")
    async def echo(payload: Payload) -> Payload:
        return payload

    return app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Run a test app with routes that fail on purpose.

    Yields:
        A client bound to the app.
    """
    async with running_app(_build_app()) as test_client:
        yield test_client


def _error(response: httpx.Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details", "request_id"}
    assert body["error"]["request_id"] == response.headers["x-request-id"]
    error: dict[str, Any] = body["error"]
    return error


@pytest.mark.parametrize(
    ("kind", "status", "code"),
    [
        ("conflict", 409, "conflict"),
        ("custom", 404, "not_found"),
        ("ai", 503, "ai_provider_unavailable"),
        ("operational", 503, "database_unavailable"),
        ("pool", 503, "database_unavailable"),
        ("teapot", 418, "i'm_a_teapot"),
        ("http-detail", 401, "unauthenticated"),
        ("crash", 500, "internal_error"),
    ],
)
async def test_errors_use_the_envelope(
    client: httpx.AsyncClient, kind: str, status: int, code: str
) -> None:
    response = await client.get(f"/fail/{kind}")

    assert response.status_code == status
    assert _error(response)["code"] == code


async def test_app_error_keeps_message_and_details(client: httpx.AsyncClient) -> None:
    conflict = _error(await client.get("/fail/conflict"))
    custom = _error(await client.get("/fail/custom"))

    assert conflict["details"] == {"field": "slug"}
    assert custom["message"] == "Tenant not found."
    assert _error(await client.get("/fail/http-detail"))["message"] == "Bad token."


async def test_unexpected_errors_hide_their_message(client: httpx.AsyncClient) -> None:
    error = _error(await client.get("/fail/crash"))

    assert "customer text" not in error["message"]


async def test_framework_errors_use_the_envelope(client: httpx.AsyncClient) -> None:
    missing = await client.get("/does-not-exist")
    wrong_method = await client.delete("/echo")

    assert (missing.status_code, _error(missing)["code"]) == (404, "not_found")
    assert wrong_method.status_code == 405
    assert _error(wrong_method)["code"] == "method_not_allowed"


async def test_validation_errors_list_fields_without_input(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/echo", json={"name": "secret value", "count": "x"})

    error = _error(response)
    assert response.status_code == 422
    assert error["code"] == "validation_error"
    assert error["details"]["errors"] == [
        {
            "loc": ["body", "count"],
            "msg": "Input should be a valid integer, unable to parse string as an"
            " integer",
            "type": "int_parsing",
        }
    ]
    assert "secret value" not in response.text


@pytest.mark.parametrize(
    ("error_class", "status"),
    [
        (BadRequestError, 400),
        (AuthenticationError, 401),
        (PermissionDeniedError, 403),
        (NotFoundError, 404),
        (ConflictError, 409),
        (AppError, 500),
    ],
)
def test_error_classes_have_codes_and_defaults(
    error_class: type[AppError], status: int
) -> None:
    error = error_class()

    assert error.status_code == status
    assert error.message == error_class.default_message
    assert error.details == {}
    assert error.code.islower()
