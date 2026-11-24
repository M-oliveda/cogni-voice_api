# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the FastAPI dependency wiring."""

import uuid
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI

from app.ai.fake import FakeEmbeddingModel, FakeLLMProvider
from app.ai.providers import EmbeddingProvider, LLMProvider
from app.core.config import Settings
from app.db.session import ANONYMOUS, TenantContext
from app.dependencies.db import get_tenant_context
from app.dependencies.providers import (
    get_embedding_provider,
    get_llm_provider,
    get_task_queue,
)
from app.dependencies.state import AppState, get_settings
from app.main import create_app
from app.services.task_queue.base import TaskQueue
from tests.conftest import make_settings, running_app


class RecordingQueue(TaskQueue):
    """Test double recording enqueued interactions."""

    def __init__(self) -> None:
        self.enqueued: list[uuid.UUID] = []

    async def enqueue_process_interaction(
        self, interaction_id: uuid.UUID, request_id: str | None
    ) -> None:
        self.enqueued.append(interaction_id)


def _app() -> FastAPI:
    app = create_app(make_settings())

    @app.get("/wiring")
    async def wiring(
        settings: Annotated[Settings, Depends(get_settings)],
        llm: Annotated[LLMProvider, Depends(get_llm_provider)],
        embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
        context: Annotated[TenantContext, Depends(get_tenant_context)],
    ) -> dict[str, object]:
        return {
            "env": settings.app_env.value,
            "llm": type(llm).__name__,
            "embeddings": type(embeddings).__name__,
            "anonymous": context is ANONYMOUS,
            "same": llm is _state(app).llm_provider,
        }

    @app.post("/enqueue")
    async def enqueue(
        queue: Annotated[TaskQueue, Depends(get_task_queue)],
    ) -> dict[str, int]:
        await queue.enqueue_process_interaction(uuid.uuid4(), None)
        return {"queued": 1}

    return app


def _state(app: FastAPI) -> AppState:
    state: AppState = app.state.cognivoice
    return state


async def test_providers_are_built_once_and_reused() -> None:
    app = _app()
    async with running_app(app) as client:
        first = (await client.get("/wiring")).json()
        second = (await client.get("/wiring")).json()

    assert first == {
        "env": "local",
        "llm": FakeLLMProvider.__name__,
        "embeddings": FakeEmbeddingModel.__name__,
        "anonymous": True,
        "same": True,
    }
    assert second == first


async def test_task_queue_must_be_configured() -> None:
    app = _app()
    async with running_app(app) as client:
        with pytest.raises(RuntimeError, match="TASK_QUEUE_BACKEND=db"):
            get_task_queue(_state(app))

        queue = RecordingQueue()
        _state(app).task_queue = queue
        response = await client.post("/enqueue")

    assert response.json() == {"queued": 1}
    assert len(queue.enqueued) == 1
