# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the deterministic fake AI provider."""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from app.ai.fake import (
    DEFAULT_DIMENSIONS,
    FAKE_MODEL_NAME,
    FakeChatModel,
    FakeEmbeddingModel,
    FakeLLMProvider,
)
from app.ai.providers import EmbeddingProvider, LLMProvider


def test_embedding_has_default_dimensions_and_model_name() -> None:
    model = FakeEmbeddingModel()

    assert isinstance(model, EmbeddingProvider)
    assert len(model.embed("hello")) == DEFAULT_DIMENSIONS == model.dimensions == 768
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


async def test_documents_keep_order_and_match_queries() -> None:
    model = FakeEmbeddingModel(dimensions=4)

    documents = await model.embed_documents(["a", "b"])

    assert documents == [model.embed("a"), model.embed("b")]
    assert await model.embed_query("a") == documents[0]


@pytest.mark.parametrize("dimensions", [0, -1])
def test_embedding_rejects_non_positive_dimensions(dimensions: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        FakeEmbeddingModel(dimensions=dimensions)


async def test_chat_replays_scripted_replies_then_echoes() -> None:
    tool_call = AIMessage(
        "", tool_calls=[{"name": "get_top_topics", "args": {"limit": 3}, "id": "1"}]
    )
    model = FakeChatModel(replies=['{"score": 0.5}', tool_call])

    first = await model.ainvoke("first")
    second = model.invoke([HumanMessage("second")])
    third = await model.ainvoke("third")

    assert first.content == '{"score": 0.5}'
    assert second.tool_calls[0]["name"] == "get_top_topics"
    assert third.content == "fake reply (5 chars)"
    assert [call[0].content for call in model.calls] == ["first", "second", "third"]


def test_llm_provider_exposes_one_chat_model() -> None:
    provider = FakeLLMProvider(replies=["ok"])

    assert isinstance(provider, LLMProvider)
    assert (provider.name, provider.model_name) == ("fake", FAKE_MODEL_NAME)
    assert provider.chat_model() is provider.chat_model()
    assert provider.chat_model().invoke("hi").content == "ok"


def test_bind_tools_records_names_and_returns_the_model() -> None:
    @tool
    def get_top_topics(limit: int) -> str:
        """Return the top topics.

        Args:
            limit: How many topics.
        """
        return str(limit)

    def search_feedback(query: str) -> str:
        return query

    model = FakeChatModel()

    assert model.bind_tools([get_top_topics, search_feedback]) is model
    assert model.bound_tools == ["get_top_topics", "search_feedback"]
