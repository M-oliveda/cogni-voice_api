# SPDX-License-Identifier: GPL-2.0-or-later
"""Walking skeleton: the deployed shape answers over real HTTP (Phase 1)."""

# Fixtures that depend on other fixtures take them as same-named parameters.
# pylint: disable=redefined-outer-name

import httpx

from tests.e2e.conftest import Stack


def test_probes_report_healthy(api: httpx.Client) -> None:
    assert api.get("/healthz").json() == {"status": "ok"}

    ready = api.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["checks"] == {"database": "ok"}


def test_documentation_is_served(api: httpx.Client) -> None:
    schema = api.get("/api/v1/openapi.json").json()

    assert schema["info"]["title"] == "CogniVoice API v1"
    assert {"/healthz", "/readyz"} <= schema["paths"].keys()
    assert api.get("/api/v1/docs").status_code == 200
    assert api.get("/api/v1/redoc").status_code == 200
    assert api.get("/docs").headers["location"] == "/api/v1/docs"


def test_unknown_route_returns_the_envelope_with_the_request_id(
    api: httpx.Client,
) -> None:
    response = api.get("/api/v1/nothing-here", headers={"X-Request-ID": "e2e-1"})

    assert response.status_code == 404
    assert response.headers["x-request-id"] == "e2e-1"
    assert response.json()["error"] == {
        "code": "not_found",
        "message": "Not Found",
        "details": {},
        "request_id": "e2e-1",
    }


def test_supabase_auth_is_reachable_through_the_gateway(stack: Stack) -> None:
    response = httpx.get(
        f"{stack.supabase_url}/auth/v1/health",
        headers={"apikey": stack.anon_key},
        timeout=10,
    )

    assert response.status_code == 200
