# SPDX-License-Identifier: GPL-2.0-or-later
"""Guards for the CI/CD workflows (MASTERPLAN.md §13.2 and §13.3).

Rule: no deployment without a passing test gate. These tests fail when a
deploy workflow stops depending on the gate, when production loses its tag or
approval path, or when any workflow plans or applies Terraform.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = Path(__file__).parents[2] / ".github" / "workflows"
DEPLOY_WORKFLOWS = {
    "deploy-dev.yml": "development",
    "deploy-stg.yml": "staging",
    "deploy-prod.yml": "production",
}
PINNED_ACTION = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


def load(name: str) -> dict[Any, Any]:
    workflow: dict[Any, Any] = yaml.safe_load((WORKFLOWS / name).read_text())
    return workflow


def triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    # YAML 1.1 reads the bare key `on` as the boolean True.
    on: dict[str, Any] = workflow[True]
    return on


def step_names(workflow: dict[Any, Any], job: str) -> list[str]:
    return [step["name"] for step in workflow["jobs"][job]["steps"]]


@pytest.mark.parametrize(("name", "environment"), DEPLOY_WORKFLOWS.items())
def test_every_deployment_needs_the_full_test_gate(name: str, environment: str) -> None:
    jobs = load(name)["jobs"]

    assert jobs["test"]["uses"] == "./.github/workflows/_test.yml"
    assert "test" in jobs["deploy"]["needs"]
    assert jobs["deploy"]["uses"] == "./.github/workflows/_deploy.yml"
    assert jobs["deploy"]["with"]["environment"] == environment
    assert jobs["deploy"]["secrets"] == "inherit"


def test_only_development_migrates_the_shared_database() -> None:
    migrating = {
        name
        for name in DEPLOY_WORKFLOWS
        if load(name)["jobs"]["deploy"]["with"].get("run-migrations", False)
    }

    assert migrating == {"deploy-dev.yml"}


def test_triggers_follow_gitflow() -> None:
    assert triggers(load("deploy-dev.yml"))["push"] == {"branches": ["develop"]}
    assert triggers(load("deploy-stg.yml"))["push"] == {"branches": ["release/**"]}
    prod = triggers(load("deploy-prod.yml"))
    assert prod == {"push": {"tags": ["v*.*.*"]}}


def test_production_requires_a_tag_on_main() -> None:
    jobs = load("deploy-prod.yml")["jobs"]

    assert set(jobs["deploy"]["needs"]) == {"test", "on-main"}
    script = jobs["on-main"]["steps"][-1]["run"]
    assert "merge-base --is-ancestor" in script


def test_traffic_moves_only_after_the_smoke_test() -> None:
    workflow = load("_deploy.yml")
    names = step_names(workflow, "deploy")
    deploy_step = workflow["jobs"]["deploy"]["steps"][
        names.index("Deploy a revision without traffic")
    ]

    assert "--no-traffic" in deploy_step["run"]
    assert names.index("Run the database migrations") < names.index(
        "Deploy a revision without traffic"
    )
    assert names.index("Deploy a revision without traffic") < names.index(
        "Smoke test the new revision"
    )
    assert names[-1] == "Shift all traffic to the new revision"


def test_deployments_authenticate_without_keys() -> None:
    deploy = load("_deploy.yml")["jobs"]["deploy"]
    auth = next(
        step
        for step in deploy["steps"]
        if step.get("uses", "").startswith("google-github-actions/auth@")
    )

    assert deploy["permissions"]["id-token"] == "write"
    assert set(auth["with"]) == {"workload_identity_provider", "service_account"}


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_workflows_never_plan_apply_or_use_keys(path: Path) -> None:
    text = path.read_text()

    assert not re.search(r"terraform\s+(plan|apply)\b", text)
    assert "credentials_json" not in text
    assert "GCP_SA_KEY" not in text


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_third_party_actions_are_pinned_by_commit(path: Path) -> None:
    for job in yaml.safe_load(path.read_text())["jobs"].values():
        for step in job.get("steps", []):
            action = step.get("uses")
            if action is not None:
                assert PINNED_ACTION.match(action), f"{path.name}: {action}"
