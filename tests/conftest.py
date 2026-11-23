# SPDX-License-Identifier: GPL-2.0-or-later
"""Shared pytest configuration for every test suite."""

from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).parent
SUITE_MARKERS = frozenset(
    {"unit", "integration", "rls", "contract", "agent", "e2e", "evals", "load"}
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark each test with the suite named by its top-level folder.

    This lets ``pytest -m unit`` (``make test-unit``) select a suite without
    decorating every test.

    Args:
        items: The collected test items.
    """
    for item in items:
        suite = item.path.relative_to(TESTS_ROOT).parts[0]
        if suite in SUITE_MARKERS:
            item.add_marker(suite)
