# SPDX-License-Identifier: GPL-2.0-or-later
"""Typed access to the objects the lifespan stores on ``app.state``."""

from dataclasses import dataclass, field

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.ai.providers import EmbeddingProvider, LLMProvider
from app.core.config import Settings
from app.services.task_queue.base import TaskQueue


@dataclass
class AppState:
    """Process-wide objects shared by every request.

    Providers and the task queue are built lazily, on first use.
    """

    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    llm_provider: LLMProvider | None = field(default=None)
    embedding_provider: EmbeddingProvider | None = field(default=None)
    task_queue: TaskQueue | None = field(default=None)


def get_app_state(request: Request) -> AppState:
    """Return the application state of the running app.

    Args:
        request: The current request.

    Returns:
        The state stored by the lifespan.
    """
    state: AppState = request.app.state.cognivoice
    return state


def get_settings(request: Request) -> Settings:
    """Return the settings the application was created with.

    Args:
        request: The current request.

    Returns:
        The settings.
    """
    return get_app_state(request).settings
