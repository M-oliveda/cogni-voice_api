<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# SQL diagnostics

Read-only queries for incidents (`MASTERPLAN.md` §22.2). Run them from the Supabase SQL editor as the operator, never as `cognivoice_app` with a forged tenant context. Do not read tenant text during an incident without a recorded reason.

## Connections

```sql
SELECT usename, application_name, state, count(*)
FROM pg_stat_activity
GROUP BY 1, 2, 3
ORDER BY 4 DESC;
```

## Long-running and idle-in-transaction sessions

```sql
SELECT pid, usename, state, now() - xact_start AS transaction_age, left(query, 80) AS query
FROM pg_stat_activity
WHERE state <> 'idle' AND xact_start < now() - interval '1 minute'
ORDER BY transaction_age DESC;
-- Terminate one only after recording it: SELECT pg_terminate_backend(<pid>);
```

## Migration state

```sql
SELECT version_num FROM alembic_version;
```

## Role and RLS integrity

```sql
SELECT rolname, rolcanlogin, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'cognivoice_app';

SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY 1;
```

Tenant tables and processing queries (`processing_error`, stuck rows) are added here as their phases land.
