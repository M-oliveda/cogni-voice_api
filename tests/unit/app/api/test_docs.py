# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for per-version API documentation."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI

from app.api.docs import ApiVersion, build_openapi, register_docs

V1 = ApiVersion(major=1, prefix="/api/v1")
V2 = ApiVersion(major=2, prefix="/api/v2")


def _app() -> FastAPI:
    app = FastAPI(
        title="Test API",
        version="9.9.9",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
        swagger_ui_parameters={"persistAuthorization": True},
    )

    @app.get("/healthz")
    async def health() -> None:
        """System route, documented in every version."""

    @app.get("/api/v1/items")
    async def v1_items() -> None:
        """A v1 operation."""

    @app.get("/api/v2/items")
    async def v2_items() -> None:
        """A v2 operation."""

    @app.get("/api/v10/items")
    async def v10_items() -> None:
        """A prefix that only looks like v1."""

    register_docs(app, [V1, V2])
    return app


@asynccontextmanager
async def _client(root_path: str = "") -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=_app(), root_path=root_path)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client


def test_version_urls_live_under_the_prefix() -> None:
    assert (V1.openapi_url, V1.docs_url, V1.redoc_url) == (
        "/api/v1/openapi.json",
        "/api/v1/docs",
        "/api/v1/redoc",
    )


@pytest.mark.parametrize(
    ("path", "documented"),
    [
        ("/api/v1/items", True),
        ("/healthz", True),
        ("/api/v1", False),
        ("/api/v10/items", False),
        ("/api/v2/items", False),
    ],
)
def test_a_version_documents_its_routes_and_system_routes(
    path: str, documented: bool
) -> None:
    assert V1.documents(path) is documented


@pytest.mark.parametrize(
    ("version", "paths"),
    [(V1, {"/healthz", "/api/v1/items"}), (V2, {"/healthz", "/api/v2/items"})],
)
def test_each_schema_holds_only_its_version(
    version: ApiVersion, paths: set[str]
) -> None:
    schema = build_openapi(_app(), version)

    assert schema["paths"].keys() == paths
    assert schema["info"]["title"] == f"Test API v{version.major}"
    assert schema["info"]["version"] == "9.9.9"


async def test_the_schema_is_served_and_cached() -> None:
    async with _client() as client:
        first = await client.get("/api/v2/openapi.json")
        second = await client.get("/api/v2/openapi.json")

    assert first.status_code == 200
    assert first.json() == second.json()
    assert "/api/v2/items" in first.json()["paths"]


@pytest.mark.parametrize(
    ("path", "marker"),
    [
        ("/api/v1/docs", '"persistAuthorization": true'),
        ("/api/v1/redoc", "redoc"),
    ],
)
async def test_docs_pages_load_their_own_schema(path: str, marker: str) -> None:
    async with _client() as client:
        response = await client.get(path)

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "/api/v1/openapi.json" in response.text
    assert marker in response.text


@pytest.mark.parametrize(
    ("path", "target"), [("/docs", "/api/v2/docs"), ("/redoc", "/api/v2/redoc")]
)
async def test_root_docs_redirect_to_the_latest_version(path: str, target: str) -> None:
    async with _client() as client:
        response = await client.get(path)

    assert response.status_code == 307
    assert response.headers["location"] == target


async def test_root_path_prefixes_schema_links_and_redirects() -> None:
    async with _client(root_path="/proxy/") as client:
        page = (await client.get("/api/v1/docs")).text
        redirect = await client.get("/docs")

    assert "/proxy/api/v1/openapi.json" in page
    assert redirect.headers["location"] == "/proxy/api/v2/docs"


async def test_there_is_no_combined_root_schema() -> None:
    async with _client() as client:
        assert (await client.get("/openapi.json")).status_code == 404
