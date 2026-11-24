# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the local ``.env`` generator."""

import stat
from pathlib import Path

import jwt
import pytest

from scripts.generate_local_env import (
    API_KEY_LIFETIME_SECONDS,
    TemplateError,
    generate_values,
    main,
    render,
    sign_api_key,
)

REPO_ROOT = Path(__file__).parents[3]
ISSUED_AT = 1_700_000_000


def parse_env(content: str) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in content.splitlines()
        if line and not line.startswith("#")
    )


def test_api_key_is_a_long_lived_role_jwt() -> None:
    token = sign_api_key("anon", "a-local-secret-that-is-long-enough", ISSUED_AT)

    claims = jwt.decode(
        token,
        "a-local-secret-that-is-long-enough",
        algorithms=["HS256"],
        options={"verify_exp": False},
    )
    assert claims == {
        "role": "anon",
        "iss": "supabase",
        "iat": ISSUED_AT,
        "exp": ISSUED_AT + API_KEY_LIFETIME_SECONDS,
    }


def test_generated_values_are_consistent() -> None:
    values = generate_values(ISSUED_AT)

    assert f":{values['COGNIVOICE_APP_DB_PASSWORD']}@" in values["DATABASE_URL"]
    assert values["DATABASE_URL"].startswith("postgresql+asyncpg://cognivoice_app:")
    assert f":{values['POSTGRES_PASSWORD']}@" in values["DATABASE_MIGRATION_URL"]
    for name, role in (
        ("SUPABASE_ANON_KEY", "anon"),
        ("SUPABASE_SERVICE_ROLE_KEY", "service_role"),
    ):
        claims = jwt.decode(
            values[name],
            values["SUPABASE_JWT_SECRET"],
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
        assert claims["role"] == role


def test_each_run_generates_new_secrets() -> None:
    first, second = generate_values(ISSUED_AT), generate_values(ISSUED_AT)

    assert all(value != second[name] for name, value in first.items())


def test_render_fills_assignments_and_keeps_everything_else() -> None:
    template = "# comment\nAPP_ENV=local\n\nSECRET=\n"

    assert render(template, {"SECRET": "value"}) == (
        "# comment\nAPP_ENV=local\n\nSECRET=value\n"
    )


def test_render_rejects_a_template_without_a_generated_variable() -> None:
    with pytest.raises(TemplateError, match="NEW_SECRET"):
        render("APP_ENV=local\n", {"NEW_SECRET": "value"})


def test_env_example_declares_every_generated_variable() -> None:
    template = (REPO_ROOT / ".env.example").read_text()

    rendered = parse_env(render(template, generate_values(ISSUED_AT)))

    assert set(generate_values(ISSUED_AT)) <= set(rendered)


def test_main_writes_an_owner_only_env_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    example = tmp_path / ".env.example"
    example.write_text((REPO_ROOT / ".env.example").read_text())
    output = tmp_path / ".env"

    assert main(["--example", str(example), "--output", str(output)]) == 0

    assert parse_env(output.read_text())["SUPABASE_JWT_SECRET"]
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert "new local secrets" in capsys.readouterr().out


def test_main_refuses_to_overwrite_without_force(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / ".env"
    output.write_text("KEEP=me\n")

    assert main(["--output", str(output)]) == 1

    assert output.read_text() == "KEEP=me\n"
    assert "--force" in capsys.readouterr().err


def test_main_with_force_replaces_and_restricts_the_file(tmp_path: Path) -> None:
    example = tmp_path / ".env.example"
    example.write_text((REPO_ROOT / ".env.example").read_text())
    output = tmp_path / ".env"
    output.write_text("OLD=value\n")
    output.chmod(0o644)

    assert main(["--example", str(example), "--output", str(output), "--force"]) == 0

    assert "OLD=value" not in output.read_text()
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


def test_main_reports_an_incomplete_template(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    example = tmp_path / ".env.example"
    example.write_text("APP_ENV=local\n")
    output = tmp_path / ".env"

    assert main(["--example", str(example), "--output", str(output)]) == 1

    assert not output.exists()
    assert "missing from .env.example" in capsys.readouterr().err
