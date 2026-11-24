# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the post-deploy smoke test."""

from collections.abc import Callable

import httpx
import pytest

from scripts.smoke_test import SmokeCheckError, build_checks, expect_ready, main

BASE_URL = "https://cognivoice-api-1.us-central1.run.app"
READY_BODY = {"status": "ok", "checks": {"database": "ok"}}

Handler = Callable[[httpx.Request], httpx.Response]


def healthy(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/readyz":
        return httpx.Response(200, json=READY_BODY)
    return httpx.Response(200, text="ok")


def run(handler: Handler, *extra: str) -> tuple[int, list[float]]:
    sleeps: list[float] = []
    code = main(
        ["--base-url", f"{BASE_URL}/", "--delay", "0.5", *extra],
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )
    return code, sleeps


def test_healthy_revision_passes(capsys: pytest.CaptureFixture[str]) -> None:
    code, sleeps = run(healthy, "--expect-docs")

    assert code == 0
    assert not sleeps
    out = capsys.readouterr().out
    assert "PASS  liveness (/healthz)" in out
    assert "PASS  readiness (/readyz)" in out
    assert "PASS  docs (/api/v1/docs)" in out


def test_docs_are_only_checked_when_expected() -> None:
    assert [check.path for check in build_checks(expect_docs=False)] == [
        "/healthz",
        "/readyz",
    ]


def test_a_cold_start_is_retried_until_it_passes() -> None:
    calls = {"count": 0}

    def cold_then_healthy(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz" and calls["count"] < 2:
            calls["count"] += 1
            raise httpx.ConnectError("connection refused")
        return healthy(request)

    code, sleeps = run(cold_then_healthy)

    assert code == 0
    assert sleeps == [0.5, 0.5]


def test_an_unready_database_fails_after_every_attempt(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unready(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/readyz":
            return httpx.Response(503, json={"error": {"code": "x"}})
        return healthy(request)

    code, sleeps = run(unready, "--attempts", "3")

    assert code == 1
    assert sleeps == [0.5, 0.5]
    assert "FAIL  readiness (/readyz): expected HTTP 200, got 503" in (
        capsys.readouterr().err
    )


def test_a_transport_error_without_a_message_is_named(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def silent_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("")

    code, _ = run(silent_timeout, "--attempts", "1")

    assert code == 1
    assert "FAIL  liveness (/healthz): ReadTimeout" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(200, text="not json"), "no checks.database"),
        (httpx.Response(200, json={"status": "ok"}), "no checks.database"),
        (httpx.Response(200, json=["ok"]), "no checks.database"),
        (
            httpx.Response(200, json={"checks": {"database": "down"}}),
            "database check is 'down'",
        ),
    ],
)
def test_readiness_needs_a_healthy_database_check(
    response: httpx.Response, message: str
) -> None:
    with pytest.raises(SmokeCheckError, match=message):
        expect_ready(response)


def test_attempts_must_be_positive(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--base-url", BASE_URL, "--attempts", "0"])

    assert exit_info.value.code == 2
    assert "--attempts must be at least 1" in capsys.readouterr().err
