-- SPDX-License-Identifier: GPL-2.0-or-later
--
-- Local only: the login role the API connects as (MASTERPLAN.md §6.3). It is
-- not a superuser and cannot bypass Row Level Security. Grants and the role's
-- timeouts are applied by the Alembic migrations, the same as in the cloud,
-- where the role's password is set by the environment setup scripts.
\set app_password `echo "$COGNIVOICE_APP_DB_PASSWORD"`

CREATE ROLE cognivoice_app
    LOGIN
    PASSWORD :'app_password'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    NOBYPASSRLS;
