# SPDX-License-Identifier: GPL-2.0-or-later
"""Post-deploy smoke test of a CogniVoice revision (MASTERPLAN.md §13.2).

The deploy workflow runs it against the new revision's tagged URL before any
traffic is shifted to it, so a failing check leaves the previous revision
serving. It checks liveness, readiness (database reachable), and, when docs
are enabled, the versioned Swagger UI. Each check is retried to absorb a cold
start. The live ingest -> analysis check is added with the cloud pipeline
(Phase 5).

Usage: ``python scripts/smoke_test.py --base-url https://... [--expect-docs]``.
"""

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import httpx

DEFAULT_ATTEMPTS = 5
DEFAULT_DELAY_SECONDS = 3.0
DEFAULT_TIMEOUT_SECONDS = 10.0


class SmokeCheckError(Exception):
    """Raised when an endpoint answers, but not with the expected response."""


@dataclass(frozen=True)
class Check:
    """One endpoint to probe and how to validate its response."""

    name: str
    path: str
    validate: Callable[[httpx.Response], None]


def expect_ok(response: httpx.Response) -> None:
    """Accept only a ``200`` response.

    Args:
        response: The endpoint's response.

    Raises:
        SmokeCheckError: When the status code is not 200.
    """
    if response.status_code != httpx.codes.OK:
        raise SmokeCheckError(f"expected HTTP 200, got {response.status_code}")


def expect_ready(response: httpx.Response) -> None:
    """Accept a ``200`` readiness response whose database check is ``ok``.

    Args:
        response: The ``/readyz`` response.

    Raises:
        SmokeCheckError: When the status is not 200 or the database is not ok.
    """
    expect_ok(response)
    try:
        database = response.json()["checks"]["database"]
    except (ValueError, KeyError, TypeError) as error:
        raise SmokeCheckError("readiness body has no checks.database") from error
    if database != "ok":
        raise SmokeCheckError(f"database check is {database!r}")


def build_checks(expect_docs: bool) -> list[Check]:
    """List the checks for this environment.

    Args:
        expect_docs: Whether ``/api/v1/docs`` must be served.

    Returns:
        The checks in the order they run.
    """
    checks = [
        Check("liveness", "/healthz", expect_ok),
        Check("readiness", "/readyz", expect_ready),
    ]
    if expect_docs:
        checks.append(Check("docs", "/api/v1/docs", expect_ok))
    return checks


def run_check(
    client: httpx.Client,
    check: Check,
    attempts: int,
    delay: float,
    sleep: Callable[[float], None] = time.sleep,
) -> str | None:
    """Run one check, retrying until it passes or the attempts run out.

    Args:
        client: HTTP client bound to the revision's base URL.
        check: The check to run.
        attempts: Maximum number of tries (at least 1).
        delay: Seconds to wait between tries.
        sleep: Sleep function, replaceable in tests.

    Returns:
        ``None`` when the check passed, otherwise the last failure reason.
    """
    reason = "not run"
    for attempt in range(1, attempts + 1):
        try:
            check.validate(client.get(check.path))
        except (httpx.HTTPError, SmokeCheckError) as error:
            reason = str(error) or type(error).__name__
            if attempt < attempts:
                sleep(delay)
        else:
            return None
    return reason


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse the command line.

    Args:
        argv: Arguments without the program name; ``None`` reads ``sys.argv``.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", required=True, help="revision URL to test")
    parser.add_argument(
        "--expect-docs",
        action="store_true",
        help="also require /api/v1/docs (when DOCS_ENABLED=true)",
    )
    parser.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    if args.attempts < 1:
        parser.error("--attempts must be at least 1")
    return args


def main(
    argv: Sequence[str] | None = None,
    transport: httpx.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Run every smoke check and report the result.

    Args:
        argv: Command-line arguments; ``None`` reads ``sys.argv``.
        transport: HTTP transport, replaceable in tests.
        sleep: Sleep function, replaceable in tests.

    Returns:
        ``0`` when every check passed, ``1`` otherwise.
    """
    args = parse_args(argv)
    failed = False
    with httpx.Client(
        base_url=args.base_url.rstrip("/"),
        timeout=args.timeout,
        transport=transport,
    ) as client:
        for check in build_checks(args.expect_docs):
            reason = run_check(client, check, args.attempts, args.delay, sleep)
            if reason is None:
                print(f"PASS  {check.name} ({check.path})")
            else:
                failed = True
                print(f"FAIL  {check.name} ({check.path}): {reason}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
