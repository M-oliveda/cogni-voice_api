# SPDX-License-Identifier: GPL-2.0-or-later
"""Base class of the tenant-scoped repositories (MASTERPLAN.md §4.2, §6.3).

Repositories are the only place SQL lives. They get the tenant from the
:class:`~app.db.session.TenantContext` of their session, never from callers,
and still filter by it explicitly: Row Level Security is the safety net, not
the only control.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import TenantContext


class MissingTenantContextError(RuntimeError):
    """A tenant-scoped repository was used without a tenant in its context."""


class TenantScopedRepository:
    """Holds the session and tenant context of one unit of work."""

    def __init__(self, session: AsyncSession, context: TenantContext) -> None:
        """Create the repository.

        Args:
            session: A session opened with
                :func:`~app.db.session.open_scoped_session` for ``context``.
            context: The tenant context of that session.
        """
        self._session = session
        self._context = context

    @property
    def session(self) -> AsyncSession:
        """The session of the unit of work."""
        return self._session

    @property
    def tenant_id(self) -> uuid.UUID:
        """The tenant every query must filter on.

        Raises:
            MissingTenantContextError: When the context has no tenant.
        """
        if self._context.tenant_id is None:
            raise MissingTenantContextError("this repository needs a tenant context")
        return self._context.tenant_id
