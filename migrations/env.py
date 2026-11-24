# SPDX-License-Identifier: GPL-2.0-or-later
"""Alembic environment (MASTERPLAN.md §13.5).

Migrations run as the admin role from ``DATABASE_MIGRATION_URL`` (or the
``sqlalchemy.url`` option, which tests set). Every migration transaction sets
``lock_timeout`` and ``statement_timeout`` so blocked DDL fails fast instead of
queueing behind traffic. Autogenerate only compares our own schemas; the ones
Supabase manages (``auth``, ``storage``, ``extensions``...) are ignored.
"""

import asyncio
from logging.config import fileConfig
from typing import Any, Literal

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  # pylint: disable=unused-import  # registers models
from app.core.config import MigrationSettings
from app.db.base import Base

config = context.config
if config.config_file_name is not None and config.attributes.get(
    "configure_logger", True
):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# Schemas owned by this project's migrations.
MANAGED_SCHEMAS = frozenset({None, "public", "app"})
LOCK_TIMEOUT = "3s"
STATEMENT_TIMEOUT = "60s"


def _database_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    settings = MigrationSettings()
    return settings.database_migration_url.get_secret_value()


def include_name(
    name: str | None,
    type_: Literal[
        "schema",
        "table",
        "column",
        "index",
        "unique_constraint",
        "foreign_key_constraint",
    ],
    parent_names: Any,
) -> bool:
    """Limit autogenerate to the schemas this project manages.

    Args:
        name: Name of the reflected object.
        type_: Kind of object.
        parent_names: Names of the enclosing objects (unused).

    Returns:
        Whether autogenerate should consider the object.
    """
    del parent_names
    if type_ == "schema":
        return name in MANAGED_SCHEMAS
    return True


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        compare_type=True,
    )


def run_migrations_offline() -> None:
    """Emit the migration SQL without connecting (``alembic upgrade --sql``)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection: Connection) -> None:
    _configure(connection)
    with context.begin_transaction():
        connection.execute(text(f"SET lock_timeout = '{LOCK_TIMEOUT}'"))
        connection.execute(text(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'"))
        context.run_migrations()


async def run_migrations_online() -> None:
    """Connect with asyncpg and run the pending migrations."""
    engine = create_async_engine(
        _database_url(),
        poolclass=pool.NullPool,
        connect_args={"statement_cache_size": 0},
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run_sync)
            await connection.commit()
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
