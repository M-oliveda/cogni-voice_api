# SPDX-License-Identifier: GPL-2.0-or-later
"""AI provider interfaces (MASTERPLAN.md §9.1).

Services and the agent depend on these abstractions only. Gemini (cloud),
Ollama (local) and the deterministic ``fake`` provider implement them. Chat is
exposed as a LangChain chat model, so the analysis service and the LangGraph
agent share one abstraction.
"""

import abc

from langchain_core.language_models import BaseChatModel


class ProviderNotConfiguredError(RuntimeError):
    """The selected provider is unknown or not available in this build."""


class LLMProvider(abc.ABC):
    """A chat model provider."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Provider name, for example ``gemini``; stored with agent runs."""

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Model identifier, stored with every analysis result."""

    @abc.abstractmethod
    def chat_model(self) -> BaseChatModel:
        """Return the LangChain chat model of this provider.

        Returns:
            The chat model.
        """


class EmbeddingProvider(abc.ABC):
    """A text embedding provider.

    Queries and documents are embedded separately because providers treat them
    differently (Gemini task types, Ollama prefixes); that difference stays
    inside each implementation.
    """

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Model identifier, stored with every vector; search filters on it."""

    @property
    @abc.abstractmethod
    def dimensions(self) -> int:
        """Length of every returned vector."""

    @abc.abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed texts that will be stored and searched.

        Args:
            texts: The texts to embed.

        Returns:
            One vector per text, in order.
        """

    @abc.abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Embed a search query.

        Args:
            text: The query.

        Returns:
            The query vector.
        """
