-- SPDX-License-Identifier: GPL-2.0-or-later
--
-- Local only: give the Supabase service roles the local POSTGRES_PASSWORD.
-- Adapted from Supabase's self-hosting setup (docker/volumes/db/roles.sql).
\set pgpass `echo "$POSTGRES_PASSWORD"`

ALTER USER authenticator WITH PASSWORD :'pgpass';
ALTER USER supabase_auth_admin WITH PASSWORD :'pgpass';
ALTER USER postgres WITH PASSWORD :'pgpass';
