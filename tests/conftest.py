# SPDX-License-Identifier: GPL-2.0-or-later
"""Shared pytest configuration for every test suite."""

# Fixtures that depend on other fixtures take them as same-named parameters.
# pylint: disable=redefined-outer-name

import asyncio
import re
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer

from app.core.config import Settings

TESTS_ROOT = Path(__file__).parent
REPO_ROOT = TESTS_ROOT.parent
APP_ROLE_SQL = REPO_ROOT / "supabase" / "volumes" / "db" / "cognivoice_app.sql"
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
# Throwaway password of cognivoice_app in the test container.
APP_TEST_PASSWORD = "app-test"  # nosec B105


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add ``--update-openapi-snapshot`` for the contract suite.

    Updating the snapshot is a deliberate, reviewed act (MASTERPLAN.md §7.8).

    Args:
        parser: The pytest option parser.
    """
    parser.addoption(
        "--update-openapi-snapshot",
        action="store_true",
        default=False,
        help="Rewrite tests/contract/openapi.v<major>.snapshot.json from the app.",
    )


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


@dataclass(frozen=True)
class DatabaseUrls:
    """Connection URLs of a migrated test database.

    Attributes:
        migration: The ``postgres`` role, as ``DATABASE_MIGRATION_URL``.
        app: The ``cognivoice_app`` role, as ``DATABASE_URL``.
    """

    migration: str
    app: str


def app_role_statements(password: str) -> list[str]:
    """Return the local init SQL of ``cognivoice_app`` with a literal password.

    The test database runs the same file as the Compose ``db`` service, so the
    role's attributes and grants cannot drift between them.

    Args:
        password: The role's password.

    Returns:
        The SQL statements, without comments or ``psql`` meta-commands.
    """
    sql = re.sub(r"^(--|\\).*$", "", APP_ROLE_SQL.read_text(), flags=re.MULTILINE)
    sql = sql.replace(":'app_password'", f"'{password}'")
    return [statement for statement in sql.split(";") if statement.strip()]


def alembic_config(url: str) -> Config:
    """Return an Alembic configuration pointing at ``url``.

    Args:
        url: The migration URL.

    Returns:
        The configuration; it leaves the test logging setup alone.
    """
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    return config


async def _prepare_roles(admin_url: str) -> None:
    engine = create_async_engine(admin_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(
            text(f"ALTER USER postgres WITH PASSWORD '{POSTGRES_TEST_PASSWORD}'")
        )
        for statement in app_role_statements(APP_TEST_PASSWORD):
            await connection.execute(text(statement))
    await engine.dispose()


@pytest.fixture(scope="session")
def database_urls(admin_database_url: str) -> DatabaseUrls:
    """Create the Supabase roles like Compose does and migrate to head.

    Migrations run as ``postgres``, as ``make migrate`` and the cloud job do.

    Args:
        admin_database_url: The superuser URL.

    Returns:
        The migration and application URLs.
    """
    asyncio.run(_prepare_roles(admin_database_url))
    admin = make_url(admin_database_url)
    migration = admin.set(username="postgres", password=POSTGRES_TEST_PASSWORD)
    app = admin.set(username="cognivoice_app", password=APP_TEST_PASSWORD)
    urls = DatabaseUrls(
        migration=migration.render_as_string(hide_password=False),
        app=app.render_as_string(hide_password=False),
    )
    command.upgrade(alembic_config(urls.migration), "head")
    return urls


def make_settings(**overrides: object) -> Settings:
    """Build settings for tests without reading ``.env`` or the environment.

    Args:
        **overrides: Values replacing the test defaults.

    Returns:
        Settings for ``APP_ENV=local`` with the ``fake`` provider.
    """
    values: dict[str, object] = {
        "database_url": "postgresql+asyncpg://cognivoice_app:x@127.0.0.1:1/postgres",
        "app_env": "local",
        "ai_provider": "fake",
        "task_queue_backend": "db",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


@pytest.fixture
async def app_engine(database_urls: DatabaseUrls) -> AsyncIterator[AsyncEngine]:
    """Create an engine connected as ``cognivoice_app``, disposed after the test.

    Args:
        database_urls: URLs of the migrated database.

    Yields:
        The engine.
    """
    engine = create_async_engine(
        database_urls.app,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
    )
    yield engine
    await engine.dispose()


@asynccontextmanager
async def running_app(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Run ``app``'s lifespan and yield an HTTP client bound to it.

    Args:
        app: The application.

    Yields:
        A client sending requests to ``app`` in-process.
    """
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client
