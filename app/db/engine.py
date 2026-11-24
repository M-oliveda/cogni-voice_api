# SPDX-License-Identifier: GPL-2.0-or-later
"""Async engine and session factory (MASTERPLAN.md §12.3, §20.2)."""

import uuid

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def _statement_name() -> str:
    return f"__asyncpg_{uuid.uuid4()}__"


def create_engine(settings: Settings) -> AsyncEngine:
    """Create the application engine, connected as ``cognivoice_app``.

    The prepared-statement caches are disabled and statement names are unique
    in every environment: Supabase's transaction pooler cannot keep prepared
    statements between transactions, and local behaviour should match the
    cloud.

    Args:
        settings: The application settings.

    Returns:
        The engine; dispose it on shutdown.
    """
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
        echo=settings.db_echo,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": _statement_name,
        },
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the session factory bound to ``engine``.

    Args:
        engine: The application engine.

    Returns:
        A factory of sessions that keep loaded objects usable after commit.
    """
    return async_sessionmaker(engine, expire_on_commit=False)
