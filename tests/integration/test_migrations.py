# SPDX-License-Identifier: GPL-2.0-or-later
"""Migration tests: up, down, up, and no drift between models and schema."""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from tests.conftest import DatabaseUrls, alembic_config


def test_upgrade_downgrade_upgrade(database_urls: DatabaseUrls) -> None:
    config = alembic_config(database_urls.migration)

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.downgrade(config, "-1")
    command.upgrade(config, "head")


def _diff(connection: Connection) -> list[object]:
    context = MigrationContext.configure(
        connection,
        opts={
            "include_schemas": True,
            "include_name": lambda name, type_, _: (
                type_ != "schema" or name in {None, "public", "app"}
            ),
        },
    )
    return list(compare_metadata(context, Base.metadata))


async def test_models_match_the_migrated_schema(database_urls: DatabaseUrls) -> None:
    engine = create_async_engine(database_urls.migration, poolclass=NullPool)
    async with engine.connect() as connection:
        diff = await connection.run_sync(_diff)
    await engine.dispose()

    assert not diff


async def test_vector_extension_is_installed(admin_engine: AsyncEngine) -> None:
    async with admin_engine.connect() as connection:
        schema = await connection.scalar(
            text(
                "SELECT n.nspname FROM pg_extension e"
                " JOIN pg_namespace n ON n.oid = e.extnamespace"
                " WHERE e.extname = 'vector'"
            )
        )

    assert schema == "extensions"


async def test_app_role_cannot_bypass_rls(
    admin_engine: AsyncEngine, database_urls: DatabaseUrls
) -> None:
    del database_urls  # the role exists once the database is migrated
    async with admin_engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT rolsuper, rolbypassrls, rolcreaterole, rolconfig"
                    " FROM pg_roles WHERE rolname = 'cognivoice_app'"
                )
            )
        ).one()

    assert not row.rolsuper
    assert not row.rolbypassrls
    assert not row.rolcreaterole
    assert "statement_timeout=5s" in row.rolconfig
    assert "idle_in_transaction_session_timeout=30s" in row.rolconfig


async def test_app_role_gets_dml_on_new_tables(
    database_urls: DatabaseUrls, app_engine: AsyncEngine
) -> None:
    owner = create_async_engine(database_urls.migration, poolclass=NullPool)
    async with owner.begin() as connection:
        await connection.execute(text("CREATE TABLE grant_probe (id int)"))
    try:
        async with app_engine.begin() as connection:
            await connection.execute(text("INSERT INTO grant_probe VALUES (1)"))
            count = await connection.scalar(text("SELECT count(*) FROM grant_probe"))
        assert count == 1
    finally:
        async with owner.begin() as connection:
            await connection.execute(text("DROP TABLE grant_probe"))
        await owner.dispose()
