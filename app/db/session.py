# SPDX-License-Identifier: GPL-2.0-or-later
"""Scoped sessions carrying the Row Level Security context (MASTERPLAN.md §6.3).

Each unit of work runs in one transaction that first sets, transaction-locally:

* ``app.tenant_id``: read by the tenant policies through
  ``app.current_tenant_id()``; when it is empty no tenant rows are visible.
* ``app.role``: read through ``app.current_user_role()`` by the policies of
  ``tenants`` and ``users`` only.
* ``statement_timeout``: so a slow query cannot hold a pooled connection.

``set_config(..., true)`` is parameterised and scoped to the transaction, so the
context cannot leak to the next user of a pooled connection, including through
Supabase's transaction pooler.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Who the current unit of work runs for.

    Built from the authenticated request (from Phase 3), never from user or
    LLM input.

    Attributes:
        tenant_id: The caller's tenant, or ``None`` (no tenant rows visible).
        role: The caller's role, for example ``super_admin``.
    """

    tenant_id: uuid.UUID | None = None
    role: str | None = None


ANONYMOUS = TenantContext()


async def apply_context(
    session: AsyncSession, context: TenantContext, statement_timeout_ms: int
) -> None:
    """Set the RLS context and statement timeout for the open transaction.

    Args:
        session: A session with an open transaction.
        context: The tenant context to apply.
        statement_timeout_ms: Statement timeout for this transaction.
    """
    tenant = str(context.tenant_id) if context.tenant_id else ""
    await session.execute(
        select(
            func.set_config("app.tenant_id", tenant, True),
            func.set_config("app.role", context.role or "", True),
            func.set_config("statement_timeout", str(statement_timeout_ms), True),
        )
    )


@asynccontextmanager
async def open_scoped_session(
    sessionmaker: async_sessionmaker[AsyncSession],
    context: TenantContext,
    statement_timeout_ms: int,
) -> AsyncIterator[AsyncSession]:
    """Open a session whose single transaction carries ``context``.

    The transaction commits when the block exits normally and rolls back when
    it raises.

    Args:
        sessionmaker: The session factory.
        context: The tenant context for the transaction.
        statement_timeout_ms: Statement timeout for the transaction.

    Yields:
        The session.
    """
    async with sessionmaker() as session, session.begin():
        await apply_context(session, context, statement_timeout_ms)
        yield session
