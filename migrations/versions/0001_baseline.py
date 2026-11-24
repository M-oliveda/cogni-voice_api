# SPDX-License-Identifier: GPL-2.0-or-later
"""Baseline: pgvector, the application role, grants, and RLS helpers.

Revision ID: 0001
Revises:
Create Date: 2026-11-24

MASTERPLAN.md §6.3: the API connects as ``cognivoice_app`` (not a superuser,
``NOBYPASSRLS``, not a table owner). Locally its login and password come from
``supabase/volumes/db/cognivoice_app.sql``, in the cloud from the environment
setup scripts; this migration only creates it (without login) when missing, so
grants never fail. Tables created later by the migration role are granted to it
automatically through default privileges, and each tenant table still ships its
own policies and ``FORCE ROW LEVEL SECURITY`` (§13.5).

The helpers return NULL when the setting is missing or empty, so a policy such
as ``tenant_id = app.current_tenant_id()`` shows no rows without a tenant
context (fail closed).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "cognivoice_app"
# Role defaults (§20.2); each transaction also sets statement_timeout itself.
ROLE_STATEMENT_TIMEOUT = "5s"
ROLE_IDLE_IN_TRANSACTION_TIMEOUT = "30s"


def upgrade() -> None:
    """Apply the migration."""
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")

    op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE}
                    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                    NOREPLICATION NOBYPASSRLS;
            END IF;
        END
        $$
        """)  # nosec B608  # only the APP_ROLE module constant is interpolated
    op.execute(
        f"ALTER ROLE {APP_ROLE} SET statement_timeout = '{ROLE_STATEMENT_TIMEOUT}'"
    )
    op.execute(
        f"ALTER ROLE {APP_ROLE} SET idle_in_transaction_session_timeout"
        f" = '{ROLE_IDLE_IN_TRANSACTION_TIMEOUT}'"
    )

    op.execute("CREATE SCHEMA app")
    op.execute("""
        CREATE FUNCTION app.current_tenant_id() RETURNS uuid
            LANGUAGE sql STABLE PARALLEL SAFE
            SET search_path = ''
            AS $$ SELECT nullif(current_setting('app.tenant_id', true), '')::uuid $$
        """)
    op.execute("""
        CREATE FUNCTION app.current_user_role() RETURNS text
            LANGUAGE sql STABLE PARALLEL SAFE
            SET search_path = ''
            AS $$ SELECT nullif(current_setting('app.role', true), '') $$
        """)
    op.execute("REVOKE ALL ON SCHEMA app FROM PUBLIC")
    op.execute("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA app FROM PUBLIC")

    for schema in ("public", "app", "extensions"):
        op.execute(f"GRANT USAGE ON SCHEMA {schema} TO {APP_ROLE}")
    op.execute(f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app TO {APP_ROLE}")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public"
        f" GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public"
        f" GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}"
    )


def downgrade() -> None:
    """Revert the migration.

    The ``vector`` extension and the ``cognivoice_app`` role are kept: the
    extension may be used outside this project's schemas, and the role is a
    login role managed outside migrations.
    """
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public"
        f" REVOKE USAGE, SELECT ON SEQUENCES FROM {APP_ROLE}"  # nosec B608
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public"
        f" REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {APP_ROLE}"
    )
    for schema in ("extensions", "public"):
        op.execute(f"REVOKE USAGE ON SCHEMA {schema} FROM {APP_ROLE}")
    op.execute("DROP SCHEMA app CASCADE")
    op.execute(f"ALTER ROLE {APP_ROLE} RESET idle_in_transaction_session_timeout")
    op.execute(f"ALTER ROLE {APP_ROLE} RESET statement_timeout")
