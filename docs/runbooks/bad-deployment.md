<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Bad deployment

**Default severity:** SEV2 (SEV1 if production is fully down) (see [incident response](incident-response.md)). Source: `MASTERPLAN.md` §22.1.

## Symptoms

- Error-rate or latency spike in the Cloud Run console right after a rollout
- The deploy workflow's smoke test failed (traffic was then never shifted)
- `/readyz` returns `503` on the live URL

## Impact

Requests served by the new revision fail. A failed smoke test means the previous revision still serves all traffic, so users are not affected.

## Diagnosis

Set the environment first: `PROJECT=moliveda-gcloudprojects-<dev|stg|prod>`, `REGION=us-central1`, `SERVICE=cognivoice-api`, `QUEUE=cognivoice-interactions`.

1. List revisions and traffic: `gcloud run services describe $SERVICE --project=$PROJECT --region=$REGION --format='yaml(status.traffic)'`
2. Read the new revision's errors: `gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="cognivoice-api" AND severity>=ERROR' --project=$PROJECT --limit=50 --freshness=1h`
3. Compare the deployed image digest with the commit in the deploy run (`Tag the image for this release` step)
4. Startup failures that mention settings mean a missing or invalid GitHub variable or secret

## Remediation

1. Shift traffic back: `gcloud run services update-traffic $SERVICE --project=$PROJECT --region=$REGION --to-revisions=<previous-revision>=100`
2. No schema rollback is needed: migrations are expand/contract (`MASTERPLAN.md` §13.5)
3. Fix forward on a branch; the next merge redeploys through the test gate

## Verification

- `make smoke URL=<service URL>` passes
- The error rate in the Cloud Run console is back to its baseline

## Prevention

- Add a regression test or E2E scenario for the failure
- Keep the smoke test covering what broke
