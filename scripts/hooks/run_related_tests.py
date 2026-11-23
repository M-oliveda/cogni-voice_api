# SPDX-License-Identifier: GPL-2.0-or-later
"""Pre-push: run only the tests related to commits not yet on the upstream.

The full suite (with the coverage gate) runs instead when the branch has no
upstream yet or when files shared by every test changed. CI always runs the
full suite, so this hook is only a fast local feedback loop.
"""

import re
import subprocess  # nosec B404  # runs fixed git and pytest commands
import sys
from pathlib import Path, PurePosixPath

SHARED_FILES = re.compile(
    r"(^|/)conftest\.py$|^pyproject\.toml$|^requirements[^/]*\.(in|txt)$|^migrations/"
)
SOURCE_ROOTS = frozenset({"app", "scripts"})
NO_TESTS_COLLECTED = 5


def upstream_branch() -> str | None:
    """Return the upstream of the current branch.

    Returns:
        The upstream name (for example ``origin/develop``), or ``None`` when the
        branch has not been pushed yet.
    """
    result = subprocess.run(  # nosec B603 B607  # fixed git command, no shell
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def changed_files(upstream: str) -> list[str]:
    """List files changed by the commits not yet on the upstream.

    Args:
        upstream: The upstream branch name.

    Returns:
        Changed paths relative to the repository root.
    """
    result = subprocess.run(  # nosec B603 B607  # fixed git command, no shell
        ["git", "diff", "--name-only", f"{upstream}...HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def needs_full_suite(changed: list[str]) -> bool:
    """Return whether a change affects every test.

    Args:
        changed: Changed paths relative to the repository root.

    Returns:
        ``True`` when a fixture, configuration, requirements or migration file
        changed.
    """
    return any(SHARED_FILES.search(path) for path in changed)


def related_tests(
    changed: list[str],
    test_root: Path = Path("tests"),
    repo_root: Path = Path("."),
) -> list[str]:
    """Map changed files to the test files that cover them.

    ``app/**/x.py`` and ``scripts/**/x.py`` map to every ``tests/**/test_x.py``;
    changed test files that still exist are run directly.

    Args:
        changed: Changed paths relative to the repository root.
        test_root: Directory searched for matching test files.
        repo_root: Repository root used to check that changed tests exist.

    Returns:
        Sorted test file paths.
    """
    tests: set[str] = set()
    for name in changed:
        path = PurePosixPath(name)
        if path.suffix != ".py":
            continue
        if path.parts[0] == "tests":
            if path.name.startswith("test_") and (repo_root / name).exists():
                tests.add(str(repo_root / name))
        elif path.parts[0] in SOURCE_ROOTS:
            tests.update(str(test) for test in test_root.rglob(f"test_{path.stem}.py"))
    return sorted(tests)


def run_pytest(args: list[str]) -> int:
    """Run pytest with the current interpreter.

    Args:
        args: Extra pytest arguments.

    Returns:
        The pytest exit code.
    """
    command = [sys.executable, "-m", "pytest", *args]
    return subprocess.run(command, check=False).returncode  # nosec B603  # no shell


def main() -> int:
    """Run the tests related to unpushed commits.

    Returns:
        ``0`` when the tests pass or none were collected, otherwise the pytest
        exit code.
    """
    upstream = upstream_branch()
    if upstream is None:
        print("No upstream branch yet: running the full suite.", flush=True)
        code = run_pytest([])
    else:
        changed = changed_files(upstream)
        if needs_full_suite(changed):
            print("Shared files changed: running the full suite.", flush=True)
            code = run_pytest([])
        else:
            tests = related_tests(changed)
            if not tests:
                print("No tests related to the unpushed commits.")
                return 0
            code = run_pytest(["--no-cov", *tests])

    if code in (0, NO_TESTS_COLLECTED):
        return 0
    print(f"Push aborted: tests failed (pytest exit code {code}).", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
