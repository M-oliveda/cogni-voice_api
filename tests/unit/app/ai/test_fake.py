# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the deterministic fake AI provider."""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.ai.fake import (
    DEFAULT_DIMENSIONS,
    FAKE_MODEL_NAME,
    FakeChatModel,
    FakeEmbeddingModel,
)


def test_embedding_has_default_dimensions_and_model_name() -> None:
    model = FakeEmbeddingModel()

    assert len(model.embed("hello")) == DEFAULT_DIMENSIONS == 768
    assert model.model_name == FAKE_MODEL_NAME


@given(st.text(), st.integers(min_value=1, max_value=50))
def test_embedding_is_deterministic_and_unit_length(text: str, dims: int) -> None:
    model = FakeEmbeddingModel(dimensions=dims)

    vector = model.embed(text)

    assert vector == model.embed(text)
    assert len(vector) == dims
    assert math.isclose(math.fsum(value * value for value in vector), 1.0)


def test_different_texts_get_different_embeddings() -> None:
    model = FakeEmbeddingModel()

    assert model.embed("billing") != model.embed("shipping")


def test_embed_many_keeps_order() -> None:
    model = FakeEmbeddingModel(dimensions=4)

    assert model.embed_many(["a", "b"]) == [model.embed("a"), model.embed("b")]


@pytest.mark.parametrize("dimensions", [0, -1])
def test_embedding_rejects_non_positive_dimensions(dimensions: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        FakeEmbeddingModel(dimensions=dimensions)


def test_chat_replays_scripted_replies_then_echoes() -> None:
    model = FakeChatModel(replies=['{"score": 0.5}'])

    assert model.complete("first") == '{"score": 0.5}'
    assert model.complete("second") == "fake reply (6 chars)"
    assert model.prompts == ["first", "second"]
    assert model.model_name == FAKE_MODEL_NAME


def test_chat_without_replies_echoes() -> None:
    assert FakeChatModel().complete("abc") == "fake reply (3 chars)"
