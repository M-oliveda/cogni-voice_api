# SPDX-License-Identifier: GPL-2.0-or-later
"""E2E harness: the real API over HTTP against the local Supabase services.

Start the services first (CI does the same)::

    make env                                   # once
    docker compose up -d --wait db auth kong

The harness migrates the Compose database as ``postgres``, then serves the
application with uvicorn in a background thread (so coverage sees it) on a free
local port, connected as ``cognivoice_app`` with the ``fake`` AI provider.

When the services are not running the suite is skipped, unless
``E2E_REQUIRED=1`` (set in CI), which turns that into a failure.
"""

# Fixtures that depend on other fixtures take them as same-named parameters.
# pylint: disable=redefined-outer-name

import asyncio
import os
import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import asyncpg
import httpx
import pytest
import uvicorn
from alembic import command
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

from app.main import create_app
from tests.conftest import alembic_config, make_settings

REPO_ROOT = Path(__file__).parents[2]
STARTUP_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class Stack:
    """Addresses of the running E2E stack.

    Attributes:
        api_url: Base URL of the API under test.
        supabase_url: The Supabase gateway (Kong).
        anon_key: The local ``anon`` API key for the gateway.
    """

    api_url: str
    supabase_url: str
    anon_key: str


def _environment() -> dict[str, str]:
    values = {
        key: value
        for key, value in dotenv_values(REPO_ROOT / ".env").items()
        if value is not None
    }
    values.update(os.environ)
    return values


def _unavailable(reason: str) -> None:
    if os.environ.get("E2E_REQUIRED") == "1":
        pytest.fail(f"E2E stack required but unavailable: {reason}")
    pytest.skip(f"E2E stack unavailable: {reason}")


async def _probe(url: str) -> None:
    parsed = make_url(url)
    connection = await asyncpg.connect(
        host=parsed.host,
        port=parsed.port,
        user=parsed.username,
        password=parsed.password,
        database=parsed.database,
        timeout=3,
    )
    await connection.close()


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


@pytest.fixture(scope="session")
def stack() -> Iterator[Stack]:
    """Migrate the Compose database and serve the API for the session.

    Yields:
        The stack addresses.
    """
    env = _environment()
    app_url = env.get("DATABASE_URL")
    migration_url = env.get("DATABASE_MIGRATION_URL")
    if not app_url or not migration_url:
        _unavailable("DATABASE_URL and DATABASE_MIGRATION_URL are not set (make env)")
    assert app_url and migration_url  # narrowed for type checkers
    try:
        asyncio.run(_probe(app_url))
    except (OSError, asyncpg.PostgresError) as error:  # OSError covers timeouts
        _unavailable(f"cannot connect to the database ({type(error).__name__})")

    command.upgrade(alembic_config(migration_url), "head")

    settings = make_settings(database_url=app_url)
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(settings),
            host="127.0.0.1",
            port=port,
            log_config=None,
            lifespan="on",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            pytest.fail("uvicorn did not start")
        time.sleep(0.05)
    try:
        yield Stack(
            api_url=f"http://127.0.0.1:{port}",
            supabase_url=env.get("SUPABASE_URL", "http://127.0.0.1:54321"),
            anon_key=env.get("SUPABASE_ANON_KEY", ""),
        )
    finally:
        server.should_exit = True
        thread.join(timeout=STARTUP_TIMEOUT_SECONDS)


@pytest.fixture
def api(stack: Stack) -> Iterator[httpx.Client]:
    """Return an HTTP client for the API under test.

    Args:
        stack: The running stack.

    Yields:
        The client.
    """
    with httpx.Client(base_url=stack.api_url, timeout=10) as client:
        yield client
