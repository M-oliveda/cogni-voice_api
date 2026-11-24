# SPDX-License-Identifier: GPL-2.0-or-later
"""AI provider and task queue dependencies, built lazily from settings."""

from typing import Annotated

from fastapi import Depends

from app.ai.factory import build_embedding_provider, build_llm_provider
from app.ai.providers import EmbeddingProvider, LLMProvider
from app.dependencies.state import AppState, get_app_state
from app.services.task_queue.base import TaskQueue


def get_llm_provider(
    state: Annotated[AppState, Depends(get_app_state)],
) -> LLMProvider:
    """Return the chat provider, building it on first use.

    Args:
        state: The application state.

    Returns:
        The provider selected by ``AI_PROVIDER``.
    """
    if state.llm_provider is None:
        state.llm_provider = build_llm_provider(state.settings)
    return state.llm_provider


def get_embedding_provider(
    state: Annotated[AppState, Depends(get_app_state)],
) -> EmbeddingProvider:
    """Return the embedding provider, building it on first use.

    Args:
        state: The application state.

    Returns:
        The provider selected by ``AI_PROVIDER``.
    """
    if state.embedding_provider is None:
        state.embedding_provider = build_embedding_provider(state.settings)
    return state.embedding_provider


def get_task_queue(state: Annotated[AppState, Depends(get_app_state)]) -> TaskQueue:
    """Return the task queue selected by ``TASK_QUEUE_BACKEND``.

    The implementations land in Phases 4 and 5; until then a queue must be set
    on the state (tests do so).

    Args:
        state: The application state.

    Returns:
        The task queue.

    Raises:
        RuntimeError: When no task queue is configured.
    """
    if state.task_queue is None:
        raise RuntimeError(
            f"TASK_QUEUE_BACKEND={state.settings.task_queue_backend.value} "
            "is not available yet"
        )
    return state.task_queue
