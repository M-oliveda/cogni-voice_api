# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for structured logging and the redaction filter."""

# Fixtures that depend on other fixtures take them as same-named parameters.
# pylint: disable=redefined-outer-name

import json
import logging
import sys
from collections.abc import Iterator

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.logging import (
    REDACTED,
    ConsoleFormatter,
    JsonFormatter,
    RedactionFilter,
    StdoutHandler,
    configure_logging,
    redact,
)
from app.core.request_context import request_id_var, route_var, tenant_id_var
from tests.conftest import make_settings


def _remove_stdout_handler() -> None:
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h, StdoutHandler)]
    logging.getLogger("uvicorn.access").disabled = False


def _record(message: str = "hello", **extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        "app.test", logging.INFO, __file__, 1, message, None, None
    )
    for name, value in extra.items():
        setattr(record, name, value)
    return record


@pytest.fixture
def request_context() -> Iterator[None]:
    """Bind a request ID, tenant and route for the duration of a test.

    Yields:
        Nothing.
    """
    tokens = (
        request_id_var.set("req-1"),
        tenant_id_var.set("tenant-1"),
        route_var.set("/healthz"),
    )
    yield
    route_var.reset(tokens[2])
    tenant_id_var.reset(tokens[1])
    request_id_var.reset(tokens[0])


@pytest.mark.usefixtures("request_context")
def test_json_lines_carry_the_required_fields() -> None:
    line = JsonFormatter("staging").format(
        _record(status_code=200, latency_ms=1.5, unknown="dropped")
    )

    payload = json.loads(line)
    assert payload["severity"] == "INFO"
    assert payload["message"] == "hello"
    assert payload["app_env"] == "staging"
    assert payload["request_id"] == "req-1"
    assert payload["tenant_id"] == "tenant-1"
    assert payload["route"] == "/healthz"
    assert payload["status_code"] == 200
    assert payload["latency_ms"] == 1.5
    assert payload["timestamp"].endswith("+00:00")
    assert "unknown" not in payload


def test_json_lines_outside_a_request_have_null_context() -> None:
    payload = json.loads(JsonFormatter("local").format(_record()))

    assert payload["request_id"] is None
    assert "exception" not in payload


@pytest.mark.usefixtures("request_context")
def test_console_lines_are_readable() -> None:
    line = ConsoleFormatter().format(_record(status_code=404))

    assert "INFO" in line
    assert "[req-1] app.test: hello status_code=404" in line


def test_console_lines_without_context() -> None:
    assert "[-] app.test: hello" in ConsoleFormatter().format(_record())


def _failing_record() -> logging.LogRecord:
    try:
        raise ValueError("token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl")
    except ValueError:
        record = _record("failed")
        record.exc_info = sys.exc_info()
    return record


@pytest.mark.parametrize("formatter", [JsonFormatter("local"), ConsoleFormatter()])
def test_exceptions_are_rendered_redacted(formatter: logging.Formatter) -> None:
    record = _failing_record()
    RedactionFilter().filter(record)

    line = formatter.format(record)

    assert "ValueError" in line
    assert "eyJhbGci" not in line
    assert REDACTED in line


@pytest.mark.parametrize(
    "secret",
    [
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl",
        "cvk_prod_ab12cd_s3cr3tvalue",
        "Bearer abc.def-ghi",
    ],
)
def test_redact_masks_known_secrets(secret: str) -> None:
    masked = redact(f"before {secret} after")

    assert secret not in masked
    assert masked.startswith("before ")
    assert masked.endswith(" after")


def test_redact_masks_connection_string_passwords() -> None:
    masked = redact("url postgresql+asyncpg://cognivoice_app:hunter2@db:5432/postgres")

    assert "hunter2" not in masked
    assert f"cognivoice_app:{REDACTED}@db:5432" in masked


@given(st.text(alphabet=st.characters(categories=["L", "N"]), min_size=1))
def test_redact_keeps_ordinary_text(text: str) -> None:
    if not text.startswith("eyJ") and "cvk_" not in text:
        assert redact(text) == text


def test_filter_drops_sensitive_fields_and_masks_arguments() -> None:
    record = logging.LogRecord(
        "app.test",
        logging.INFO,
        __file__,
        1,
        "key %s",
        ("cvk_dev_abc_secret",),
        None,
    )
    record.text_content = "my email is a@b.c"
    record.prompt = "system prompt"
    record.status_code = 201

    assert RedactionFilter().filter(record) is True
    assert not hasattr(record, "text_content")
    assert not hasattr(record, "prompt")
    assert vars(record)["status_code"] == 201
    assert record.getMessage() == f"key {REDACTED}"


def test_configure_logging_uses_json_in_the_cloud(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(make_settings(log_level="WARNING"))
    configure_logging(
        make_settings(
            app_env="development",
            ai_provider="gemini",
            gemini_api_key="k",
            task_queue_backend="cloud_tasks",
            gcp_project_id="p",
            cloud_tasks_queue="q",
            cloud_tasks_invoker_sa="sa",
            service_url="https://s",
            log_level="INFO",
        )
    )
    try:
        logging.getLogger("app.test").info("cloud line", extra={"answer": "secret"})
        logging.getLogger("uvicorn.access").info("suppressed")

        lines = capsys.readouterr().out.strip().splitlines()
        assert len(lines) == 1
        assert (
            sum(isinstance(h, StdoutHandler) for h in logging.getLogger().handlers) == 1
        )
        payload = json.loads(lines[0])
        assert payload["message"] == "cloud line"
        assert payload["app_env"] == "development"
        assert "answer" not in payload
        assert logging.getLogger().level == logging.INFO
    finally:
        _remove_stdout_handler()


def test_configure_logging_uses_the_console_locally(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(make_settings(log_level="DEBUG"))
    try:
        logging.getLogger("app.test").debug("local line")

        assert "app.test: local line" in capsys.readouterr().out
    finally:
        _remove_stdout_handler()
