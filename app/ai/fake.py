# SPDX-License-Identifier: GPL-2.0-or-later
"""Deterministic ``fake`` AI provider used by unit, integration and E2E tests.

It never touches the network: the same input always produces the same output,
so tests are repeatable (MASTERPLAN.md §9.1, §17.1). Startup will reject
``AI_PROVIDER=fake`` outside ``APP_ENV=local`` once configuration lands in
Phase 1, which also makes these classes implement the provider interfaces.
"""

import hashlib
import math
import struct

DEFAULT_DIMENSIONS = 768
FAKE_MODEL_NAME = "fake-v1"


class FakeEmbeddingModel:
    """Hash-based embeddings: deterministic, L2-normalized vectors.

    Identical texts get identical vectors and different texts get unrelated
    ones, which is enough to test storage and search plumbing.
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
        self.dimensions = dimensions
        self.model_name = FAKE_MODEL_NAME

    def embed(self, text: str) -> list[float]:
        """Return the embedding of one text.

        Args:
            text: The text to embed.

        Returns:
            A unit-length vector of ``dimensions`` floats.
        """
        values: list[float] = []
        counter = 0
        while len(values) < self.dimensions:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            # Each 32-byte digest yields eight unsigned 32-bit integers.
            for number in struct.unpack(">8I", digest):
                values.append(number / 0xFFFFFFFF - 0.5)
            counter += 1
        vector = values[: self.dimensions]
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Return the embeddings of several texts, in order.

        Args:
            texts: The texts to embed.

        Returns:
            One vector per text.
        """
        return [self.embed(text) for text in texts]


class FakeChatModel:
    """Replays scripted replies, then echoes, so tests control model output."""

    def __init__(self, replies: list[str] | None = None) -> None:
        """Create the model.

        Args:
            replies: Replies returned in order by successive calls. When they
                run out, the model returns a fixed echo of the prompt length.
        """
        self._replies = list(replies or [])
        self.model_name = FAKE_MODEL_NAME
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        """Return the next scripted reply and record the prompt.

        Args:
            prompt: The prompt sent to the model.

        Returns:
            The next scripted reply, or ``"fake reply (<n> chars)"``.
        """
        self.prompts.append(prompt)
        if self._replies:
            return self._replies.pop(0)
        return f"fake reply ({len(prompt)} chars)"
