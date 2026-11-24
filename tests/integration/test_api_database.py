# SPDX-License-Identifier: GPL-2.0-or-later
"""Routes that touch the database, served as ``cognivoice_app``."""

import uuid
from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import TenantContext
from app.dependencies.db import get_session, get_tenant_context
from app.main import create_app
from tests.conftest import DatabaseUrls, make_settings, running_app

TENANT = uuid.UUID("00000000-0000-4000-8000-0000000000c1")


def _app(database_urls: DatabaseUrls) -> FastAPI:
    app = create_app(
        make_settings(database_url=database_urls.app, db_statement_timeout_ms=2500)
    )

    @app.get("/context")
    async def context(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> dict[str, str | None]:
        row = (
            await session.execute(
                text(
                    "SELECT app.current_tenant_id()::text AS tenant,"
                    " current_user AS role,"
                    " current_setting('statement_timeout') AS timeout"
                )
            )
        ).one()
        return {"tenant": row.tenant, "role": row.role, "timeout": row.timeout}

    return app


async def test_readiness_succeeds_with_a_database(
    database_urls: DatabaseUrls,
) -> None:
    async with running_app(_app(database_urls)) as client:
        response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}


async def test_session_is_anonymous_until_authentication_lands(
    database_urls: DatabaseUrls,
) -> None:
    async with running_app(_app(database_urls)) as client:
        body = (await client.get("/context")).json()

    assert body == {"tenant": None, "role": "cognivoice_app", "timeout": "2500ms"}


async def test_session_carries_the_request_tenant(
    database_urls: DatabaseUrls,
) -> None:
    app = _app(database_urls)
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=TENANT, role="tenant_viewer"
    )
    async with running_app(app) as client:
        body = (await client.get("/context")).json()

    assert body["tenant"] == str(TENANT)
