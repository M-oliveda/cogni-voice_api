# SPDX-License-Identifier: GPL-2.0-or-later
"""Refuse to commit files that must never reach the repository.

Blocks ``design/``, ``.env*`` files (except ``.env.example``), ``*.pem`` and
``*.key``. The check runs on the staged file list, so it also catches files
force-added with ``git add -f``.
"""

import re
import subprocess  # nosec B404  # runs a fixed git command, never user input
import sys

BLOCKED = re.compile(r"^design/|(^|/)\.env(\.|$)|\.(pem|key)$")
ALLOWED = re.compile(r"(^|/)\.env\.example$")


def is_blocked(path: str) -> bool:
    """Return whether a repository path is confidential.

    Args:
        path: A path relative to the repository root, using forward slashes.

    Returns:
        ``True`` when the file must not be committed.
    """
    return bool(BLOCKED.search(path)) and not ALLOWED.search(path)


def staged_files() -> list[str]:
    """List the files added, copied, modified or renamed in the index.

    Returns:
        Paths relative to the repository root.
    """
    result = subprocess.run(  # nosec B603 B607  # fixed git command, no shell
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def main() -> int:
    """Fail the commit when a confidential file is staged.

    Returns:
        ``0`` when no confidential file is staged, otherwise ``1``.
    """
    blocked = [path for path in staged_files() if is_blocked(path)]
    if not blocked:
        return 0

    print("Refusing to commit confidential or secret files:", file=sys.stderr)
    for path in blocked:
        print(f"   - {path}", file=sys.stderr)
    print("Unstage them with 'git restore --staged <file>'.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
