<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Queue backlog growing

**Default severity:** SEV2 (see [incident response](incident-response.md)). Source: `MASTERPLAN.md` §22.1.

> Applies once Phase 5 (Cloud Tasks) lands; until then this is a skeleton.

## Symptoms

- Oldest task age rising
- Interactions stay `pending` or `processing`

## Impact

Analysis results arrive late; nothing is lost because tasks are retried.

## Diagnosis

Set the environment first: `PROJECT=moliveda-gcloudprojects-<dev|stg|prod>`, `REGION=us-central1`, `SERVICE=cognivoice-api`, `QUEUE=cognivoice-interactions`.

1. Inspect the queue: `gcloud tasks queues describe $QUEUE --location=$REGION --project=$PROJECT` and `gcloud tasks list --queue=$QUEUE --location=$REGION --project=$PROJECT --limit=20`
2. Check the Gemini `429`/`5xx` ratio and Cloud Run instance errors
3. Confirm the OIDC audience (`SERVICE_URL`) and invoker account are unchanged

## Remediation

1. Pause while fixing: `gcloud tasks queues pause $QUEUE --location=$REGION --project=$PROJECT`
2. Fix the cause, then `gcloud tasks queues resume ...`
3. Do not raise the dispatch rate while Gemini is throttling

## Verification

- Oldest task age falls back under 15 minutes

## Prevention

- Re-run `infra/scripts/setup_cloud_tasks.sh <env>` to restore the §8.3 queue settings
