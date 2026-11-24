# SPDX-License-Identifier: GPL-2.0-or-later
"""The RLS context isolates tenants and never leaks between transactions.

A probe table with the same policy shape as the tenant tables of Phase 3
proves the helpers, ``open_scoped_session`` and the ``cognivoice_app`` role
work together (MASTERPLAN.md §6.3, §20.2).
"""

# Fixtures that depend on other fixtures take them as same-named parameters.
# pylint: disable=redefined-outer-name

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool

from app.db.engine import create_sessionmaker
from app.db.session import ANONYMOUS, TenantContext, open_scoped_session
from tests.conftest import DatabaseUrls

TENANT_A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
TENANT_B = uuid.UUID("00000000-0000-4000-8000-00000000000b")
TIMEOUT_MS = 5000


@pytest.fixture
async def probe_table(database_urls: DatabaseUrls) -> AsyncIterator[None]:
    """Create a tenant table with FORCE RLS and one row per tenant.

    Args:
        database_urls: URLs of the migrated database.

    Yields:
        Nothing; the table is dropped afterwards.
    """
    owner = create_async_engine(database_urls.migration, poolclass=NullPool)
    async with owner.begin() as connection:
        await connection.execute(
            text("CREATE TABLE rls_probe (tenant_id uuid NOT NULL, label text)")
        )
        await connection.execute(
            text("ALTER TABLE rls_probe ENABLE ROW LEVEL SECURITY")
        )
        await connection.execute(text("ALTER TABLE rls_probe FORCE ROW LEVEL SECURITY"))
        await connection.execute(
            text(
                "CREATE POLICY tenant_isolation ON rls_probe"
                " USING (tenant_id = app.current_tenant_id())"
                " WITH CHECK (tenant_id = app.current_tenant_id())"
            )
        )
        await connection.execute(
            text("INSERT INTO rls_probe VALUES (:a, 'a'), (:b, 'b')"),
            {"a": TENANT_A, "b": TENANT_B},
        )
    yield
    async with owner.begin() as connection:
        await connection.execute(text("DROP TABLE rls_probe"))
    await owner.dispose()


@pytest.fixture
def sessionmaker(app_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return the application session factory on the ``cognivoice_app`` engine.

    Args:
        app_engine: Engine connected as ``cognivoice_app``.

    Returns:
        The session factory.
    """
    return create_sessionmaker(app_engine)


async def _labels(
    sessionmaker: async_sessionmaker[AsyncSession], context: TenantContext
) -> list[str]:
    async with open_scoped_session(sessionmaker, context, TIMEOUT_MS) as session:
        result = await session.execute(text("SELECT label FROM rls_probe"))
        return list(result.scalars())


@pytest.mark.usefixtures("probe_table")
async def test_each_tenant_sees_only_its_rows(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    assert await _labels(sessionmaker, TenantContext(tenant_id=TENANT_A)) == ["a"]
    assert await _labels(sessionmaker, TenantContext(tenant_id=TENANT_B)) == ["b"]


@pytest.mark.usefixtures("probe_table")
async def test_missing_tenant_context_sees_no_rows(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    assert not await _labels(sessionmaker, ANONYMOUS)


@pytest.mark.usefixtures("probe_table")
async def test_super_admin_role_does_not_unlock_content(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    assert not await _labels(sessionmaker, TenantContext(role="super_admin"))


@pytest.mark.usefixtures("probe_table")
async def test_tenant_cannot_write_rows_for_another_tenant(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(DBAPIError, match="row-level security"):
        async with open_scoped_session(
            sessionmaker, TenantContext(tenant_id=TENANT_A), TIMEOUT_MS
        ) as session:
            await session.execute(
                text("INSERT INTO rls_probe VALUES (:b, 'forged')"), {"b": TENANT_B}
            )


@pytest.mark.usefixtures("probe_table")
async def test_context_does_not_leak_to_the_next_transaction(
    database_urls: DatabaseUrls,
) -> None:
    # One physical connection, reused, as a pooler would.
    engine = create_async_engine(
        database_urls.app,
        poolclass=StaticPool,
        connect_args={"statement_cache_size": 0},
    )
    single = create_sessionmaker(engine)
    try:
        assert await _labels(single, TenantContext(tenant_id=TENANT_A)) == ["a"]
        async with single() as session:
            tenant = await session.scalar(text("SELECT app.current_tenant_id()"))
            leaked = await session.scalar(text("SELECT count(*) FROM rls_probe"))
        assert tenant is None
        assert leaked == 0
    finally:
        await engine.dispose()


async def test_context_sets_role_and_statement_timeout(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    context = TenantContext(tenant_id=TENANT_A, role="tenant_admin")
    async with open_scoped_session(sessionmaker, context, 1234) as session:
        row = (
            await session.execute(
                text(
                    "SELECT app.current_tenant_id(), app.current_user_role(),"
                    " current_setting('statement_timeout')"
                )
            )
        ).one()

    assert tuple(row) == (TENANT_A, "tenant_admin", "1234ms")
