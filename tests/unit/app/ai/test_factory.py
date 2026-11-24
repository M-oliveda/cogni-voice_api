# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the AI provider factory."""

import pytest

from app.ai.factory import build_embedding_provider, build_llm_provider
from app.ai.fake import FakeEmbeddingModel, FakeLLMProvider
from app.ai.providers import ProviderNotConfiguredError
from tests.conftest import make_settings


def test_fake_provider_is_built() -> None:
    settings = make_settings(embedding_dimensions=16)

    assert isinstance(build_llm_provider(settings), FakeLLMProvider)
    embeddings = build_embedding_provider(settings)
    assert isinstance(embeddings, FakeEmbeddingModel)
    assert embeddings.dimensions == 16


@pytest.mark.parametrize(
    "settings",
    [
        make_settings(ai_provider="ollama"),
        make_settings(ai_provider="gemini", gemini_api_key="k"),
    ],
    ids=["ollama", "gemini"],
)
def test_real_providers_are_not_available_yet(settings: object) -> None:
    for build in (build_llm_provider, build_embedding_provider):
        with pytest.raises(ProviderNotConfiguredError, match="not available yet"):
            build(settings)  # type: ignore[arg-type]
