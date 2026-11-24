<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Enqueue failures

**Default severity:** SEV2 (see [incident response](incident-response.md)). Source: `MASTERPLAN.md` §22.1.

> Applies once Phase 5 (Cloud Tasks) lands; until then this is a skeleton.

## Symptoms

- Ingest returns `503`
- Rows are `failed` at creation

## Impact

Clients must retry; `external_id` idempotency makes retries safe.

## Diagnosis

Set the environment first: `PROJECT=moliveda-gcloudprojects-<dev|stg|prod>`, `REGION=us-central1`, `SERVICE=cognivoice-api`, `QUEUE=cognivoice-interactions`.

1. Check the queue exists and is running
2. Check the runtime account still has `roles/cloudtasks.enqueuer` on the queue
3. Check Cloud Tasks quotas

## Remediation

1. Re-run `infra/scripts/setup_environment.sh <env>` to restore the queue and bindings
2. Ask clients to retry the failed requests

## Verification

- A test ingest returns `202`

## Prevention

- `infra/scripts/verify_environment.sh <env>` after every manual IAM change
