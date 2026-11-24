<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Database connection exhaustion

**Default severity:** SEV2 (see [incident response](incident-response.md)). Source: `MASTERPLAN.md` §22.1.

## Symptoms

- `too many connections` or pool timeout errors in the logs
- `/readyz` returns `503` (`database_unavailable`)

## Impact

All API requests that touch the database fail. The single free Supabase database is shared by every environment, so one environment can starve the others.

## Diagnosis

Set the environment first: `PROJECT=moliveda-gcloudprojects-<dev|stg|prod>`, `REGION=us-central1`, `SERVICE=cognivoice-api`, `QUEUE=cognivoice-interactions`.

1. Compute the budget: max instances × (`DB_POOL_SIZE` + `DB_POOL_MAX_OVERFLOW`) across **all three** environments against the Supabase pooler limit (`MASTERPLAN.md` §20.2)
2. Check the Supabase dashboard (Database → Connections) for long-running or idle-in-transaction sessions
3. Check the instance count in the Cloud Run console (service → Metrics → Container instance count) for each environment

## Remediation

1. Lower `CLOUD_RUN_MAX_INSTANCES` or the pool size for the noisiest environment and redeploy
2. Terminate leaked sessions from the Supabase SQL editor (see [SQL diagnostics](sql-diagnostics.md))
3. Confirm `DATABASE_URL` uses the transaction pooler (port 6543)

## Verification

- `/readyz` returns `200` in every environment
- Connection count stays below the limit for 30 minutes

## Prevention

- Keep the per-environment connection budget documented in `MASTERPLAN.md` §20.2
