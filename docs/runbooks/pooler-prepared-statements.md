<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Pooler and prepared-statement errors

**Default severity:** SEV2 (see [incident response](incident-response.md)). Source: `MASTERPLAN.md` §22.1.

## Symptoms

- `prepared statement "..." does not exist` or `already exists` errors

## Impact

Database calls fail intermittently.

## Diagnosis

Set the environment first: `PROJECT=moliveda-gcloudprojects-<dev|stg|prod>`, `REGION=us-central1`, `SERVICE=cognivoice-api`, `QUEUE=cognivoice-interactions`.

1. Confirm `DATABASE_URL` points at the transaction pooler (port 6543), not the direct host
2. Confirm the engine still disables asyncpg's statement caches (`app/db/engine.py`; `MASTERPLAN.md` §12.3)

## Remediation

1. Fix the URL in the `DATABASE_URL` repository secret and re-run the deploy workflow
2. If the engine settings regressed, revert that change and redeploy

## Verification

- No prepared-statement errors in the logs for 30 minutes
- `make smoke URL=<service URL>` passes

## Prevention

- Integration tests keep running with statement caching disabled, matching the pooler
