# SPDX-License-Identifier: GPL-2.0-or-later
"""OpenAPI contract: a reviewed snapshot per API version and documentation rules.

Each major version has its own schema and snapshot (§7, §7.8). After an
intended API change, regenerate the snapshots with::

    .venv/bin/pytest tests/contract --no-cov --update-openapi-snapshot

and review their diff in the pull request.
"""

# Tests take the `version` fixture as a same-named parameter.
# pylint: disable=redefined-outer-name

import json
from pathlib import Path
from typing import Any

import pytest

from app.api.docs import ApiVersion, build_openapi
from app.main import API_VERSIONS, create_app
from tests.conftest import make_settings

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
# Errors every versioned operation must document with the envelope.
V1_ERROR_STATUSES = {"422", "500", "503"}


@pytest.fixture(params=API_VERSIONS, ids=lambda version: f"v{version.major}")
def version(request: pytest.FixtureRequest) -> ApiVersion:
    """Run a contract test once per served API version.

    Args:
        request: The pytest request carrying the version.

    Returns:
        The API version.
    """
    api_version: ApiVersion = request.param
    return api_version


def _schema(version: ApiVersion) -> dict[str, Any]:
    return build_openapi(create_app(make_settings()), version)


def _operations(schema: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (path, method, operation)
        for path, item in schema["paths"].items()
        for method, operation in item.items()
        if method in HTTP_METHODS
    ]


def test_openapi_matches_the_snapshot(
    request: pytest.FixtureRequest, version: ApiVersion
) -> None:
    snapshot = Path(__file__).with_name(f"openapi.v{version.major}.snapshot.json")
    rendered = json.dumps(_schema(version), indent=2, sort_keys=True) + "\n"
    if request.config.getoption("--update-openapi-snapshot"):
        snapshot.write_text(rendered, encoding="utf-8")

    assert rendered == snapshot.read_text(encoding="utf-8"), (
        "The OpenAPI schema changed. If intended, rerun with "
        "--update-openapi-snapshot and review the diff."
    )


def test_every_operation_is_documented(version: ApiVersion) -> None:
    operations = _operations(_schema(version))

    assert operations
    for path, method, operation in operations:
        where = f"{method.upper()} {path}"
        assert operation.get("operationId"), where
        assert operation.get("summary"), where
        assert operation.get("description"), where
        assert operation.get("tags"), where
        assert "200" in operation["responses"] or "201" in operation["responses"]


def test_versioned_operations_document_the_error_envelope(
    version: ApiVersion,
) -> None:
    for path, method, operation in _operations(_schema(version)):
        if not path.startswith(f"{version.prefix}/"):
            continue
        responses = operation["responses"]
        assert V1_ERROR_STATUSES <= responses.keys(), f"{method.upper()} {path}"
        for status in V1_ERROR_STATUSES:
            ref = responses[status]["content"]["application/json"]["schema"]["$ref"]
            assert ref.endswith("/ErrorResponse")


def test_operation_ids_are_unique(version: ApiVersion) -> None:
    ids = [
        operation["operationId"] for _, _, operation in _operations(_schema(version))
    ]

    assert len(ids) == len(set(ids))
