# SPDX-License-Identifier: GPL-2.0-or-later
"""Consistency checks for the local docker-compose.yaml."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.conftest import POSTGRES_IMAGE

REPO_ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module", name="services")
def services_fixture() -> dict[str, Any]:
    with (REPO_ROOT / "docker-compose.yaml").open() as file:
        services: dict[str, Any] = yaml.safe_load(file)["services"]
    return services


def test_db_image_matches_the_test_database(services: dict[str, Any]) -> None:
    assert services["db"]["image"] == POSTGRES_IMAGE


def test_api_and_worker_build_the_dev_target(services: dict[str, Any]) -> None:
    for name in ("api", "worker"):
        assert services[name]["build"]["target"] == "dev"


def test_published_ports_bind_to_localhost_only(services: dict[str, Any]) -> None:
    ports = [port for service in services.values() for port in service.get("ports", [])]

    assert ports
    assert all(str(port).startswith("127.0.0.1:") for port in ports)


def test_every_image_is_pinned_to_a_version(services: dict[str, Any]) -> None:
    images = [service["image"] for service in services.values() if "image" in service]

    assert all(":" in image and not image.endswith(":latest") for image in images)


def test_mounted_supabase_files_exist(services: dict[str, Any]) -> None:
    mounts = [
        volume.split(":")[0]
        for service in services.values()
        for volume in service.get("volumes", [])
        if volume.startswith("./supabase/")
    ]

    assert mounts
    assert all((REPO_ROOT / mount).is_file() for mount in mounts)
