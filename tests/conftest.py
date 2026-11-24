# SPDX-License-Identifier: GPL-2.0-or-later
"""Shared pytest configuration for every test suite."""

# Fixtures that depend on other fixtures take them as same-named parameters.
# pylint: disable=redefined-outer-name

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer

TESTS_ROOT = Path(__file__).parent
SUITE_MARKERS = frozenset(
    {"unit", "integration", "rls", "contract", "agent", "e2e", "evals", "load"}
)

# The same image as the ``db`` service in docker-compose.yaml (a unit test keeps
# them in sync), so tests run against Supabase's roles and extensions.
POSTGRES_IMAGE = "supabase/postgres:17.12.0.002"
# Superuser of the Supabase image; migrations run as this role.
POSTGRES_ADMIN_USER = "supabase_admin"
# Throwaway container credential, never used outside the test run.
POSTGRES_TEST_PASSWORD = "postgres-test"  # nosec B105


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark each test with the suite named by its top-level folder.

    This lets ``pytest -m unit`` (``make test-unit``) select a suite without
    decorating every test.

    Args:
        items: The collected test items.
    """
    for item in items:
        suite = item.path.relative_to(TESTS_ROOT).parts[0]
        if suite in SUITE_MARKERS:
            item.add_marker(suite)


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Start one Supabase Postgres container for the whole test session.

    The container starts only when a test requests it, so unit tests never need
    Docker.

    Yields:
        The running container.
    """
    container = PostgresContainer(
        POSTGRES_IMAGE,
        username=POSTGRES_ADMIN_USER,
        password=POSTGRES_TEST_PASSWORD,
        dbname="postgres",
        driver="asyncpg",
    )
    with container:
        yield container


@pytest.fixture(scope="session")
def admin_database_url(postgres_container: PostgresContainer) -> str:
    """Return the asyncpg URL of the container's superuser.

    Args:
        postgres_container: The running container.

    Returns:
        A ``postgresql+asyncpg://`` URL.
    """
    return postgres_container.get_connection_url()


@pytest.fixture
async def admin_engine(admin_database_url: str) -> AsyncIterator[AsyncEngine]:
    """Create an engine connected as the superuser, disposed after the test.

    ``NullPool`` keeps connections from leaking between event loops.

    Args:
        admin_database_url: The superuser URL.

    Yields:
        The engine.
    """
    engine = create_async_engine(admin_database_url, poolclass=NullPool)
    yield engine
    await engine.dispose()
