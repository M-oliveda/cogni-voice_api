# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the tenant-scoped repository base."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import ANONYMOUS, TenantContext
from app.repositories.base import MissingTenantContextError, TenantScopedRepository


def test_tenant_comes_from_the_context() -> None:
    tenant = uuid.uuid4()
    session = AsyncSession()

    repository = TenantScopedRepository(session, TenantContext(tenant_id=tenant))

    assert repository.tenant_id == tenant
    assert repository.session is session


def test_missing_tenant_fails_closed() -> None:
    repository = TenantScopedRepository(AsyncSession(), ANONYMOUS)

    with pytest.raises(MissingTenantContextError):
        _ = repository.tenant_id
