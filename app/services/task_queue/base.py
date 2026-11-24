# SPDX-License-Identifier: GPL-2.0-or-later
"""The ``TaskQueue`` interface (MASTERPLAN.md §8).

``DbPollingQueue`` (local, Phase 4) and ``CloudTasksQueue`` (cloud, Phase 5)
implement it, and both deliveries end in the same ``ProcessInteractionService``.
"""

import abc
import uuid


class EnqueueError(Exception):
    """The task could not be enqueued; the caller marks the row failed."""


class TaskQueue(abc.ABC):
    """Schedules the asynchronous processing of an interaction."""

    @abc.abstractmethod
    async def enqueue_process_interaction(
        self, interaction_id: uuid.UUID, request_id: str | None
    ) -> None:
        """Schedule processing of one interaction, at most once.

        Implementations must be idempotent: enqueueing the same interaction
        twice (task name ``process-{interaction_id}``) is a success.

        Args:
            interaction_id: The interaction to process.
            request_id: Request ID carried to the handler for correlation.

        Raises:
            EnqueueError: When the task cannot be scheduled.
        """
