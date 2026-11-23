# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the pre-push related-tests runner."""

import subprocess
import sys
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from scripts.hooks import run_related_tests
from scripts.hooks.run_related_tests import (
    changed_files,
    main,
    needs_full_suite,
    related_tests,
    run_pytest,
    upstream_branch,
)

SUBPROCESS_RUN = "scripts.hooks.run_related_tests.subprocess.run"


def _completed(
    returncode: int = 0, stdout: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout)


def test_upstream_branch_returns_name(mocker: MockerFixture) -> None:
    mocker.patch(
        SUBPROCESS_RUN,
        return_value=_completed(stdout="origin/feature/x\n"),
    )
    assert upstream_branch() == "origin/feature/x"


def test_upstream_branch_returns_none_without_upstream(
    mocker: MockerFixture,
) -> None:
    mocker.patch(SUBPROCESS_RUN, return_value=_completed(returncode=128))
    assert upstream_branch() is None


def test_changed_files_diffs_against_upstream(mocker: MockerFixture) -> None:
    run = mocker.patch(
        SUBPROCESS_RUN,
        return_value=_completed(stdout="app/a.py\ntests/unit/test_a.py\n"),
    )

    assert changed_files("origin/develop") == ["app/a.py", "tests/unit/test_a.py"]
    assert "origin/develop...HEAD" in run.call_args.args[0]


@pytest.mark.parametrize(
    "path",
    [
        "conftest.py",
        "tests/unit/conftest.py",
        "pyproject.toml",
        "requirements.in",
        "requirements-dev.txt",
        "migrations/env.py",
    ],
)
def test_needs_full_suite_for_shared_files(path: str) -> None:
    assert needs_full_suite(["app/a.py", path])


def test_needs_full_suite_false_for_regular_files() -> None:
    assert not needs_full_suite(["app/a.py", "docs/requirements.md", "README.md"])


def test_related_tests_maps_sources_and_keeps_changed_tests(tmp_path: Path) -> None:
    unit = tmp_path / "tests" / "unit"
    (unit / "services").mkdir(parents=True)
    (unit / "services" / "test_ingestion.py").write_text("", encoding="utf-8")
    (unit / "test_validate_commit_msg.py").write_text("", encoding="utf-8")
    (unit / "test_existing.py").write_text("", encoding="utf-8")
    root = tmp_path / "tests"

    result = related_tests(
        [
            "app/services/ingestion.py",
            "scripts/hooks/validate_commit_msg.py",
            "app/no_tests_for_this.py",
            "tests/unit/test_existing.py",
            "tests/unit/conftest_helpers.py",
            "tests/unit/test_deleted.py",
            "docs/notes.py",
            "README.md",
        ],
        test_root=root,
        repo_root=tmp_path,
    )

    assert result == [
        str(unit / "services" / "test_ingestion.py"),
        str(unit / "test_existing.py"),
        str(unit / "test_validate_commit_msg.py"),
    ]


def test_run_pytest_uses_current_interpreter(mocker: MockerFixture) -> None:
    run = mocker.patch(SUBPROCESS_RUN, return_value=_completed(returncode=3))

    assert run_pytest(["--no-cov", "tests/unit/test_a.py"]) == 3
    assert run.call_args.args[0] == [
        sys.executable,
        "-m",
        "pytest",
        "--no-cov",
        "tests/unit/test_a.py",
    ]


def test_main_runs_full_suite_without_upstream(mocker: MockerFixture) -> None:
    mocker.patch.object(run_related_tests, "upstream_branch", return_value=None)
    pytest_run = mocker.patch.object(run_related_tests, "run_pytest", return_value=0)

    assert main() == 0
    pytest_run.assert_called_once_with([])


def test_main_runs_full_suite_when_shared_files_changed(
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(run_related_tests, "upstream_branch", return_value="o/d")
    mocker.patch.object(
        run_related_tests, "changed_files", return_value=["pyproject.toml"]
    )
    pytest_run = mocker.patch.object(run_related_tests, "run_pytest", return_value=0)

    assert main() == 0
    pytest_run.assert_called_once_with([])


def test_main_runs_related_tests_without_coverage(mocker: MockerFixture) -> None:
    mocker.patch.object(run_related_tests, "upstream_branch", return_value="o/d")
    mocker.patch.object(run_related_tests, "changed_files", return_value=["app/a.py"])
    mocker.patch.object(
        run_related_tests, "related_tests", return_value=["tests/unit/test_a.py"]
    )
    pytest_run = mocker.patch.object(run_related_tests, "run_pytest", return_value=0)

    assert main() == 0
    pytest_run.assert_called_once_with(["--no-cov", "tests/unit/test_a.py"])


def test_main_skips_when_no_related_tests(mocker: MockerFixture) -> None:
    mocker.patch.object(run_related_tests, "upstream_branch", return_value="o/d")
    mocker.patch.object(run_related_tests, "changed_files", return_value=["README.md"])
    pytest_run = mocker.patch.object(run_related_tests, "run_pytest")

    assert main() == 0
    pytest_run.assert_not_called()


def test_main_treats_no_tests_collected_as_success(mocker: MockerFixture) -> None:
    mocker.patch.object(run_related_tests, "upstream_branch", return_value=None)
    mocker.patch.object(run_related_tests, "run_pytest", return_value=5)
    assert main() == 0


def test_main_reports_failing_tests(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch.object(run_related_tests, "upstream_branch", return_value=None)
    mocker.patch.object(run_related_tests, "run_pytest", return_value=1)

    assert main() == 1
    assert "Push aborted" in capsys.readouterr().err
