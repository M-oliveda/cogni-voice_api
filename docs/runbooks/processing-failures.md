<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# High processing failure ratio

**Default severity:** SEV2 (see [incident response](incident-response.md)). Source: `MASTERPLAN.md` §22.1.

> Applies once Phase 4 (AI analysis) lands; until then this is a skeleton.

## Symptoms

- The `failed` count rises
- `processing_error` shows a repeated pattern

## Impact

Affected interactions have no analysis until they are requeued.

## Diagnosis

Set the environment first: `PROJECT=moliveda-gcloudprojects-<dev|stg|prod>`, `REGION=us-central1`, `SERVICE=cognivoice-api`, `QUEUE=cognivoice-interactions`.

1. Group failures by `processing_error` and `prompt_version` (see [SQL diagnostics](sql-diagnostics.md))
2. Correlate with the last deployment or a model change

## Remediation

1. Roll back the prompt or model change through configuration or a traffic switch
2. Requeue the failed rows after the fix

## Verification

- The failure ratio returns to its baseline

## Prevention

- Add the failing input shape to the evaluation set
