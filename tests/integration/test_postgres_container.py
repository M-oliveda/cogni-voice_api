# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests proving the Testcontainers database matches Supabase."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_pgvector_extension_supports_cosine_distance(
    admin_engine: AsyncEngine,
) -> None:
    async with admin_engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        distance = await connection.scalar(
            text("SELECT '[1,0,0]'::vector <=> '[0,1,0]'::vector")
        )

    assert distance == 1.0


async def test_supabase_roles_exist(admin_engine: AsyncEngine) -> None:
    async with admin_engine.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT rolname FROM pg_roles"
                " WHERE rolname IN ('anon', 'authenticated', 'service_role')"
                " ORDER BY rolname"
            )
        )

    assert result.scalars().all() == ["anon", "authenticated", "service_role"]
