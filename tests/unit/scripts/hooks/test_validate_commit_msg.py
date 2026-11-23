# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the Gitmoji commit-message validator."""

from pathlib import Path

import pytest

from scripts.hooks.validate_commit_msg import MAX_FIRST_LINE_LENGTH, main, validate


@pytest.mark.parametrize(
    "message",
    [
        ":sparkles: Add semantic search endpoint",
        ":bug: Fix token validation issue\n\nLonger body explaining the fix.",
        ":white_check_mark: Add tests for the hook scripts\n",
        "# Please enter the commit message\n\n:memo: Update README",
        ":tada: " + "A" * (MAX_FIRST_LINE_LENGTH - len(":tada: ")),
    ],
)
def test_validate_accepts_valid_messages(message: str) -> None:
    assert not validate(message)


@pytest.mark.parametrize(
    "message",
    [
        "Merge branch 'develop' into feature/project-setup",
        'Revert ":sparkles: Add search"',
        "fixup! :bug: Fix token validation",
        "squash! :bug: Fix token validation",
        "amend! :bug: Fix token validation",
        "Merge branch 'a-very-long-branch-name' into another-very-long-branch-name.",
    ],
)
def test_validate_accepts_git_generated_messages(message: str) -> None:
    assert not validate(message)


@pytest.mark.parametrize("message", ["", "\n\n", "# only a comment\n"])
def test_validate_rejects_empty_message(message: str) -> None:
    assert validate(message) == ["The commit message is empty."]


@pytest.mark.parametrize(
    "message",
    ["Add search endpoint", "sparkles: Add search", ":Sparkles: Add", ":sparkles:Add"],
)
def test_validate_requires_gitmoji_prefix(message: str) -> None:
    errors = validate(message)
    assert len(errors) == 1
    assert "Gitmoji shortcode" in errors[0]


@pytest.mark.parametrize("message", [":sparkles: add search", ":sparkles: "])
def test_validate_requires_uppercase_first_letter(message: str) -> None:
    errors = validate(message)
    assert len(errors) == 1
    assert "uppercase" in errors[0]


def test_validate_rejects_trailing_period() -> None:
    errors = validate(":sparkles: Add search endpoint.")
    assert len(errors) == 1
    assert "period" in errors[0]


def test_validate_rejects_long_first_line() -> None:
    line = ":tada: " + "A" * (MAX_FIRST_LINE_LENGTH - len(":tada: ") + 1)
    errors = validate(line)
    assert len(errors) == 1
    assert "73 characters" in errors[0]


def test_validate_reports_every_broken_rule() -> None:
    errors = validate("add a very long message " + "x" * 60 + ".")
    assert len(errors) == 3


def test_main_returns_zero_for_valid_message(tmp_path: Path) -> None:
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text(":sparkles: Add search endpoint\n", encoding="utf-8")
    assert main([str(message_file)]) == 0


def test_main_reports_invalid_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text("add search endpoint.\n", encoding="utf-8")

    assert main([str(message_file)]) == 1

    err = capsys.readouterr().err
    assert "add search endpoint." in err
    assert ":sparkles: Add semantic search endpoint" in err
    assert "https://gitmoji.dev" in err


def test_main_requires_message_file_argument(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 2
    assert "Usage" in capsys.readouterr().err


def test_main_reads_sys_argv_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text(":memo: Update docs\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["hook", str(message_file)])
    assert main() == 0
