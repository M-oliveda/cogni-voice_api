# SPDX-License-Identifier: GPL-2.0-or-later
"""Liveness and readiness probes (MASTERPLAN.md §7.1); no version prefix."""

import asyncio
from typing import Annotated, Final

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.core.errors import DatabaseUnavailableError, ErrorResponse
from app.dependencies.state import AppState, get_app_state
from app.schemas.health import HealthResponse, ReadinessResponse

READINESS_TIMEOUT_SECONDS: Final = 2.0

router = APIRouter(tags=["health"])


@router.get(
    "/healthz",
    operation_id="getLiveness",
    summary="Liveness probe",
    description="Returns 200 while the process is running. Checks nothing else.",
    response_model=HealthResponse,
)
async def liveness() -> HealthResponse:
    """Report that the process is alive.

    Returns:
        ``{"status": "ok"}``.
    """
    return HealthResponse(status="ok")


@router.get(
    "/readyz",
    operation_id="getReadiness",
    summary="Readiness probe",
    description=(
        "Returns 200 when the database answers within "
        f"{READINESS_TIMEOUT_SECONDS:g} seconds, otherwise 503 with the error "
        "envelope (`database_unavailable`)."
    ),
    response_model=ReadinessResponse,
    responses={
        503: {"model": ErrorResponse, "description": "The database is unreachable"}
    },
)
async def readiness(
    state: Annotated[AppState, Depends(get_app_state)],
) -> ReadinessResponse:
    """Report whether the service can handle requests.

    Args:
        state: The application state.

    Returns:
        The readiness result.

    Raises:
        DatabaseUnavailableError: When the database does not answer in time.
    """
    # TimeoutError (from asyncio.timeout) and refused connections are OSErrors.
    try:
        async with asyncio.timeout(READINESS_TIMEOUT_SECONDS):
            async with state.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except OSError as error:
        raise DatabaseUnavailableError() from error
    return ReadinessResponse(status="ok", checks={"database": "ok"})
