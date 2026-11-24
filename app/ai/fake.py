# SPDX-License-Identifier: GPL-2.0-or-later
"""Deterministic ``fake`` AI provider used by unit, integration and E2E tests.

It never touches the network: the same input always produces the same output,
so tests are repeatable (MASTERPLAN.md §9.1, §17.1). Configuration rejects
``AI_PROVIDER=fake`` outside ``APP_ENV=local``.
"""

import hashlib
import math
import struct
from collections.abc import Callable, Sequence
from typing import Any, Final, override

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import Field

from app.ai.providers import EmbeddingProvider, LLMProvider

DEFAULT_DIMENSIONS: Final = 768
FAKE_MODEL_NAME: Final = "fake-v1"
FAKE_PROVIDER_NAME: Final = "fake"


class FakeEmbeddingModel(EmbeddingProvider):
    """Hash-based embeddings: deterministic, L2-normalized vectors.

    Identical texts get identical vectors and different texts get unrelated
    ones, which is enough to test storage and search plumbing. Queries and
    documents are embedded the same way, so searching for a stored text finds
    it with similarity 1.
    """

    def __init__(self, dimensions: int = DEFAULT_DIMENSIONS) -> None:
        """Create the model.

        Args:
            dimensions: Length of every vector; must be positive.

        Raises:
            ValueError: When ``dimensions`` is not positive.
        """
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self._dimensions = dimensions

    @property
    @override
    def model_name(self) -> str:
        return FAKE_MODEL_NAME

    @property
    @override
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        """Return the embedding of one text.

        Args:
            text: The text to embed.

        Returns:
            A unit-length vector of ``dimensions`` floats.
        """
        values: list[float] = []
        counter = 0
        while len(values) < self._dimensions:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            # Each 32-byte digest yields eight unsigned 32-bit integers.
            for number in struct.unpack(">8I", digest):
                values.append(number / 0xFFFFFFFF - 0.5)
            counter += 1
        vector = values[: self._dimensions]
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector]

    @override
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]

    @override
    async def embed_query(self, text: str) -> list[float]:
        return self.embed(text)


# ``_stream`` is optional: without it LangChain streams the ``_generate`` result.
class FakeChatModel(BaseChatModel):  # pylint: disable=abstract-method
    """LangChain chat model that replays scripted replies, then echoes.

    A scripted reply is either text or a full :class:`AIMessage`, for example
    one carrying tool calls, so tests control exactly what the model "says".
    Every call's messages are recorded in :attr:`calls`, and the tools of the
    last :meth:`bind_tools` call in :attr:`bound_tools`.
    """

    replies: list[str | AIMessage] = Field(default_factory=list)
    calls: list[list[BaseMessage]] = Field(default_factory=list)
    bound_tools: list[str] = Field(default_factory=list)

    @property
    @override
    def _llm_type(self) -> str:
        return "cognivoice-fake"

    @override
    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        """Record the tool names; scripted replies decide which tools are called.

        Args:
            tools: The tools offered to the model.
            tool_choice: Ignored.
            **kwargs: Ignored.

        Returns:
            This model.
        """
        del tool_choice, kwargs
        self.bound_tools = [
            (
                tool.name
                if isinstance(tool, BaseTool)
                else str(getattr(tool, "__name__", tool))
            )
            for tool in tools
        ]
        return self

    @override
    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls.append(list(messages))
        if self.replies:
            reply = self.replies.pop(0)
            message = reply if isinstance(reply, AIMessage) else AIMessage(reply)
        else:
            size = sum(len(str(item.content)) for item in messages)
            message = AIMessage(f"fake reply ({size} chars)")
        return ChatResult(generations=[ChatGeneration(message=message)])


class FakeLLMProvider(LLMProvider):
    """``LLMProvider`` backed by one shared :class:`FakeChatModel`."""

    def __init__(self, replies: list[str | AIMessage] | None = None) -> None:
        """Create the provider.

        Args:
            replies: Scripted replies of the chat model.
        """
        self._model = FakeChatModel(replies=list(replies or []))

    @property
    @override
    def name(self) -> str:
        return FAKE_PROVIDER_NAME

    @property
    @override
    def model_name(self) -> str:
        return FAKE_MODEL_NAME

    @override
    def chat_model(self) -> FakeChatModel:
        return self._model
