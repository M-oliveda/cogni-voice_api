# SPDX-License-Identifier: GPL-2.0-or-later
"""Database session dependency with the RLS context (MASTERPLAN.md §6.3)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import ANONYMOUS, TenantContext, open_scoped_session
from app.dependencies.state import AppState, get_app_state


def get_tenant_context() -> TenantContext:
    """Return the tenant context of the request.

    Phase 3 overrides this with the authenticated identity. Until then every
    request is anonymous, so tenant policies show no rows (fail closed).

    Returns:
        The anonymous context.
    """
    return ANONYMOUS


async def get_session(
    state: Annotated[AppState, Depends(get_app_state)],
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AsyncIterator[AsyncSession]:
    """Yield a session whose transaction carries the request's tenant context.

    Args:
        state: The application state.
        context: The request's tenant context.

    Yields:
        The session; its transaction commits after the route returns.
    """
    async with open_scoped_session(
        state.sessionmaker, context, state.settings.db_statement_timeout_ms
    ) as session:
        yield session
