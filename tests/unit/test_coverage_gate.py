# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests proving the 100% line and branch coverage gate fails builds below it."""

import json
import subprocess  # nosec B404  # runs pytest in a throwaway project
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).parents[2]

MODULE = """\
def sign(value: int) -> str:
    if value < 0:
        return "negative"
    return "non-negative"
"""
# Exercises only one branch of ``sign``: lines are covered, branches are not.
PARTIAL_TEST = """\
from pkg.mod import sign


def test_sign() -> None:
    assert sign(1) == "non-negative"
"""
FULL_TEST = PARTIAL_TEST + """

def test_negative() -> None:
    assert sign(-1) == "negative"
"""


def load_pyproject() -> dict[str, Any]:
    with (REPO_ROOT / "pyproject.toml").open("rb") as file:
        return tomllib.load(file)


def test_gate_is_configured_for_full_branch_coverage() -> None:
    config = load_pyproject()

    assert "--cov-fail-under=100" in config["tool"]["pytest"]["ini_options"]["addopts"]
    assert config["tool"]["coverage"]["run"]["branch"] is True


def run_project(tmp_path: Path, test_source: str) -> subprocess.CompletedProcess[str]:
    """Run pytest with this repository's gate settings on a tiny project."""
    addopts = load_pyproject()["tool"]["pytest"]["ini_options"]["addopts"]
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        'pythonpath = ["."]\n'
        f"addopts = {json.dumps(addopts)}\n"
        "[tool.coverage.run]\n"
        'source = ["pkg"]\n'
        "branch = true\n"
    )
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "mod.py").write_text(MODULE)
    (tmp_path / "test_mod.py").write_text(test_source)
    return subprocess.run(  # nosec B603  # fixed interpreter and arguments
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize(
    ("test_source", "passes"), [(PARTIAL_TEST, False), (FULL_TEST, True)]
)
def test_gate_fails_on_a_missed_branch(
    tmp_path: Path, test_source: str, passes: bool
) -> None:
    result = run_project(tmp_path, test_source)

    assert (result.returncode == 0) is passes, result.stdout
    if not passes:
        assert "Required test coverage of 100% not reached" in result.stdout
