# SPDX-License-Identifier: GPL-2.0-or-later
"""Provider factory: ``AI_PROVIDER`` selects the implementation (§9.1).

There is no automatic fallback between providers. Gemini and Ollama adapters
land in Phase 4; until then selecting them fails when a provider is first
needed, not at startup, so the application still starts with the local
default (``ollama``).
"""

from app.ai.fake import FakeEmbeddingModel, FakeLLMProvider
from app.ai.providers import EmbeddingProvider, LLMProvider, ProviderNotConfiguredError
from app.core.config import AIProviderName, Settings


def _not_available(provider: AIProviderName) -> ProviderNotConfiguredError:
    return ProviderNotConfiguredError(
        f"AI_PROVIDER={provider.value} is not available yet"
    )


def build_llm_provider(settings: Settings) -> LLMProvider:
    """Build the chat provider selected by ``AI_PROVIDER``.

    Args:
        settings: The application settings.

    Returns:
        The provider.

    Raises:
        ProviderNotConfiguredError: When the provider is not available.
    """
    if settings.ai_provider is AIProviderName.FAKE:
        return FakeLLMProvider()
    raise _not_available(settings.ai_provider)


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Build the embedding provider selected by ``AI_PROVIDER``.

    Args:
        settings: The application settings.

    Returns:
        The provider, producing ``EMBEDDING_DIMENSIONS``-long vectors.

    Raises:
        ProviderNotConfiguredError: When the provider is not available.
    """
    if settings.ai_provider is AIProviderName.FAKE:
        return FakeEmbeddingModel(dimensions=settings.embedding_dimensions)
    raise _not_available(settings.ai_provider)
