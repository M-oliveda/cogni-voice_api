# SPDX-License-Identifier: GPL-2.0-or-later
"""Responses of the health endpoints."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """The process is running."""

    status: Literal["ok"] = Field(examples=["ok"])


class ReadinessResponse(BaseModel):
    """The process can serve traffic: its dependencies are reachable."""

    status: Literal["ok"] = Field(examples=["ok"])
    checks: dict[str, Literal["ok"]] = Field(examples=[{"database": "ok"}])
