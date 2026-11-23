# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the confidential-file pre-commit guard."""

import subprocess

import pytest
from pytest_mock import MockerFixture

from scripts.hooks import block_confidential
from scripts.hooks.block_confidential import is_blocked, main, staged_files


@pytest.mark.parametrize(
    "path",
    [
        "design/mockup.png",
        "design/nested/spec.pdf",
        ".env",
        ".env.local",
        "infra/.env.production",
        "certs/server.pem",
        "keys/private.key",
    ],
)
def test_is_blocked_rejects_confidential_paths(path: str) -> None:
    assert is_blocked(path)


@pytest.mark.parametrize(
    "path",
    [
        ".env.example",
        "infra/.env.example",
        "app/main.py",
        "docs/design/overview.md",
        "app/env.py",
        "app/keys.py",
        "README.md",
    ],
)
def test_is_blocked_allows_regular_paths(path: str) -> None:
    assert not is_blocked(path)


def test_staged_files_lists_added_and_modified_files(mocker: MockerFixture) -> None:
    run = mocker.patch(
        "scripts.hooks.block_confidential.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, stdout="a.py\nb/.env\n"),
    )

    assert staged_files() == ["a.py", "b/.env"]
    assert run.call_args.args[0] == [
        "git",
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=ACMR",
    ]


def test_main_passes_without_confidential_files(mocker: MockerFixture) -> None:
    mocker.patch.object(
        block_confidential, "staged_files", return_value=["app/main.py"]
    )
    assert main() == 0


def test_main_blocks_confidential_files(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch.object(
        block_confidential,
        "staged_files",
        return_value=["app/main.py", ".env", "design/logo.svg", ".env.example"],
    )

    assert main() == 1

    err = capsys.readouterr().err
    assert "   - .env\n" in err
    assert "   - design/logo.svg\n" in err
    assert ".env.example" not in err
    assert "git restore --staged" in err
