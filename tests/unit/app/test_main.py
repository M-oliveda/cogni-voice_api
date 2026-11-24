# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the application factory, docs, and health endpoints."""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app import __version__
from app.api.docs import build_openapi
from app.api.v1 import API_V1
from app.dependencies.state import AppState
from app.main import create_app
from tests.conftest import make_settings, running_app

CLOUD = {
    "app_env": "production",
    "ai_provider": "gemini",
    "gemini_api_key": "k",
    "task_queue_backend": "cloud_tasks",
    "gcp_project_id": "p",
    "cloud_tasks_queue": "q",
    "cloud_tasks_invoker_sa": "sa@p.iam.gserviceaccount.com",
}


async def test_openapi_metadata() -> None:
    async with running_app(create_app(make_settings())) as client:
        schema: dict[str, Any] = (await client.get("/api/v1/openapi.json")).json()

    assert schema["info"]["title"] == "CogniVoice API v1"
    assert schema["info"]["version"] == __version__
    assert schema["info"]["license"]["identifier"] == "GPL-2.0-or-later"
    assert schema["servers"] == [
        {"url": "http://localhost:8000", "description": "local"}
    ]


@pytest.mark.parametrize("path", ["/api/v1/docs", "/api/v1/redoc"])
async def test_docs_are_served(path: str) -> None:
    async with running_app(create_app(make_settings())) as client:
        response = await client.get(path)

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


async def test_swagger_persists_authorization() -> None:
    async with running_app(create_app(make_settings())) as client:
        page = (await client.get("/api/v1/docs")).text

    assert '"persistAuthorization": true' in page


@pytest.mark.parametrize(
    ("path", "target"), [("/docs", "/api/v1/docs"), ("/redoc", "/api/v1/redoc")]
)
async def test_root_docs_redirect_to_v1(path: str, target: str) -> None:
    async with running_app(create_app(make_settings())) as client:
        response = await client.get(path)

    assert response.status_code == 307
    assert response.headers["location"] == target


@pytest.mark.parametrize(
    "path",
    [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/docs",
        "/api/v1/redoc",
        "/api/v1/openapi.json",
    ],
)
async def test_docs_can_be_disabled(path: str) -> None:
    app = create_app(make_settings(docs_enabled=False))
    async with running_app(app) as client:
        assert (await client.get(path)).status_code == 404


async def test_cloud_servers_use_the_service_url() -> None:
    settings = make_settings(**CLOUD, service_url="https://api.example.com")
    async with running_app(create_app(settings)) as client:
        schema = (await client.get("/api/v1/openapi.json")).json()

    assert schema["servers"] == [
        {"url": "https://api.example.com", "description": "production"}
    ]


def test_servers_are_empty_without_a_known_url() -> None:
    settings = make_settings(**CLOUD, service_url="https://x")
    settings.service_url = None

    assert "servers" not in build_openapi(create_app(settings), API_V1)


async def test_lifespan_creates_and_disposes_the_engine() -> None:
    app = create_app(make_settings(db_pool_size=3))
    async with running_app(app):
        state: AppState = app.state.cognivoice
        engine: AsyncEngine = state.engine
        assert engine.pool.size() == 3  # type: ignore[attr-defined]
        assert state.llm_provider is None


async def test_liveness() -> None:
    async with running_app(create_app(make_settings())) as client:
        response = await client.get("/healthz")

    assert (response.status_code, response.json()) == (200, {"status": "ok"})


async def test_readiness_fails_without_a_database() -> None:
    async with running_app(create_app(make_settings())) as client:
        response = await client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"


async def test_cors_allows_configured_origins_only() -> None:
    app = create_app(make_settings(cors_allowed_origins=["http://allowed.test"]))
    async with running_app(app) as client:
        allowed = await client.get(
            "/healthz", headers={"Origin": "http://allowed.test"}
        )
        denied = await client.get("/healthz", headers={"Origin": "http://evil.test"})

    assert allowed.headers["access-control-allow-origin"] == "http://allowed.test"
    assert "x-request-id" in allowed.headers["access-control-expose-headers"]
    assert "access-control-allow-origin" not in denied.headers
