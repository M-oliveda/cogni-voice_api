# SPDX-License-Identifier: GPL-2.0-or-later
"""Create a local ``.env`` from ``.env.example`` with freshly generated secrets.

The local Supabase services (``docker-compose.yaml``) need a database password,
a JWT secret, and the ``anon`` and ``service_role`` API keys signed with it.
Generating them per clone means no shared demo key is ever committed. The
values are for local development only; cloud secrets live in GitHub Secrets.

Usage: ``make env`` (or ``python scripts/generate_local_env.py [--force]``).
"""

import argparse
import os
import re
import secrets
import sys
import time
from pathlib import Path

import jwt

# Host port of the ``db`` service published by docker-compose.yaml.
LOCAL_DB_ADDRESS = "127.0.0.1:54322"
API_KEY_LIFETIME_SECONDS = 10 * 365 * 24 * 60 * 60
ASSIGNMENT = re.compile(r"^(?P<name>[A-Z][A-Z0-9_]*)=.*$")


class TemplateError(Exception):
    """Raised when ``.env.example`` lacks a variable this script generates."""


def sign_api_key(role: str, jwt_secret: str, issued_at: int) -> str:
    """Sign a Supabase legacy API key (an HS256 JWT carrying a role).

    Args:
        role: ``anon`` or ``service_role``.
        jwt_secret: The secret shared by Auth, the gateway and the API.
        issued_at: Issue time as a Unix timestamp.

    Returns:
        The encoded JWT.
    """
    claims = {
        "role": role,
        "iss": "supabase",
        "iat": issued_at,
        "exp": issued_at + API_KEY_LIFETIME_SECONDS,
    }
    return jwt.encode(claims, jwt_secret, algorithm="HS256")


def generate_values(issued_at: int) -> dict[str, str]:
    """Generate every local secret and the URLs that embed them.

    Args:
        issued_at: Issue time of the API keys as a Unix timestamp.

    Returns:
        Variable names mapped to their new values.
    """
    postgres_password = secrets.token_urlsafe(32)
    app_password = secrets.token_urlsafe(32)
    jwt_secret = secrets.token_urlsafe(48)
    return {
        "POSTGRES_PASSWORD": postgres_password,
        "COGNIVOICE_APP_DB_PASSWORD": app_password,
        "DATABASE_URL": (
            f"postgresql+asyncpg://cognivoice_app:{app_password}"
            f"@{LOCAL_DB_ADDRESS}/postgres"
        ),
        "DATABASE_MIGRATION_URL": (
            f"postgresql+asyncpg://postgres:{postgres_password}"
            f"@{LOCAL_DB_ADDRESS}/postgres"
        ),
        "SUPABASE_JWT_SECRET": jwt_secret,
        "SUPABASE_ANON_KEY": sign_api_key("anon", jwt_secret, issued_at),
        "SUPABASE_SERVICE_ROLE_KEY": sign_api_key(
            "service_role", jwt_secret, issued_at
        ),
        "API_KEY_HMAC_SECRET": secrets.token_urlsafe(32),
        "DASHBOARD_PASSWORD": secrets.token_urlsafe(16),
        "PG_META_CRYPTO_KEY": secrets.token_urlsafe(32),
    }


def render(template: str, values: dict[str, str]) -> str:
    """Fill the generated values into the template's assignments.

    Comments, blank lines and other variables are copied unchanged.

    Args:
        template: The contents of ``.env.example``.
        values: Variable names mapped to their new values.

    Returns:
        The contents of the new ``.env``.

    Raises:
        TemplateError: When a generated variable has no line in the template.
    """
    lines = template.splitlines()
    filled: set[str] = set()
    for index, line in enumerate(lines):
        match = ASSIGNMENT.match(line)
        if match and match["name"] in values:
            name = match["name"]
            lines[index] = f"{name}={values[name]}"
            filled.add(name)
    missing = sorted(values.keys() - filled)
    if missing:
        raise TemplateError(f"missing from .env.example: {', '.join(missing)}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line.

    Args:
        argv: Arguments without the program name; ``None`` reads ``sys.argv``.

    Returns:
        The parsed options.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--example", type=Path, default=Path(".env.example"))
    parser.add_argument("--output", type=Path, default=Path(".env"))
    parser.add_argument(
        "--force", action="store_true", help="replace an existing output file"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Write the local ``.env``.

    Args:
        argv: Arguments without the program name; ``None`` reads ``sys.argv``.

    Returns:
        ``0`` on success, ``1`` when the output exists or the template is
        incomplete.
    """
    args = parse_args(argv)
    if args.output.exists() and not args.force:
        print(
            f"{args.output} already exists; pass --force to replace it.",
            file=sys.stderr,
        )
        return 1
    try:
        content = render(
            args.example.read_text(), generate_values(issued_at=int(time.time()))
        )
    except TemplateError as error:
        print(f"Cannot create {args.output}: {error}", file=sys.stderr)
        return 1
    # Owner-only permissions: the file holds secrets.
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(descriptor, 0o600)  # also when --force replaces an existing file
    with os.fdopen(descriptor, "w") as file:
        file.write(content)
    print(f"Wrote {args.output} with new local secrets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
