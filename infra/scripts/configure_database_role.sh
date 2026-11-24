#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Creates (when missing) and enables the cognivoice_app login role on the
# Supabase database, with the same attributes as the baseline migration
# (MASTERPLAN.md §6.3). One free Supabase project serves every environment
# (decision 31), so this runs once, before the first deploy, and again only to
# rotate the password. Credentials come from the environment, never arguments:
#
#   DATABASE_MIGRATION_URL      admin (postgres) URL; the +asyncpg suffix is fine
#   COGNIVOICE_APP_DB_PASSWORD  new password for cognivoice_app
#
# Usage: configure_database_role.sh

set -euo pipefail

: "${DATABASE_MIGRATION_URL:?set DATABASE_MIGRATION_URL (admin connection)}"
: "${COGNIVOICE_APP_DB_PASSWORD:?set COGNIVOICE_APP_DB_PASSWORD}"

# psql speaks libpq URLs, not SQLAlchemy's driver suffix.
admin_url="${DATABASE_MIGRATION_URL/postgresql+asyncpg:/postgresql:}"

# The password is passed as a psql variable and quoted by psql (:'name'), so
# it is never interpolated into the SQL text or shown in the process list.
psql "$admin_url" --no-psqlrc --quiet --set=ON_ERROR_STOP=1 \
  --set=app_password="$COGNIVOICE_APP_DB_PASSWORD" <<'SQL'
SELECT NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'cognivoice_app') AS missing
\gset
\if :missing
  CREATE ROLE cognivoice_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
\endif
ALTER ROLE cognivoice_app WITH LOGIN PASSWORD :'app_password';
SQL

echo "cognivoice_app can log in; DATABASE_URL uses user cognivoice_app.<project-ref> on the pooler"
