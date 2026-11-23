# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the application package metadata."""

import re

import app


def test_version_is_semantic() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", app.__version__)
