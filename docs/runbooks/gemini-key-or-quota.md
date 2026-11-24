<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Gemini key invalid or quota exhausted

**Default severity:** SEV2 (see [incident response](incident-response.md)). Source: `MASTERPLAN.md` §22.1.

> Applies once Phase 4 (AI analysis) lands; until then this is a skeleton.

## Symptoms

- Every AI path fails with `401`, `403`, or `429` from Gemini

## Impact

Interactions stay unprocessed and the agent is unavailable; ingestion still accepts data.

## Diagnosis

Set the environment first: `PROJECT=moliveda-gcloudprojects-<dev|stg|prod>`, `REGION=us-central1`, `SERVICE=cognivoice-api`, `QUEUE=cognivoice-interactions`.

1. Find the status codes in the logs (`severity>=WARNING`, Gemini errors)
2. Check the key and its quota in Google AI Studio
3. A free-tier quota resets daily; a `429` burst may be rate limiting, not exhaustion

## Remediation

1. Rotate the key: create a new one, then `gh secret set GEMINI_API_KEY` and re-run the deploy workflow
2. Delete the old key if it may have leaked (treat a leak as SEV1)
3. For exhaustion, wait for the reset or lower the queue dispatch rate

## Verification

- A test interaction is analysed end to end

## Prevention

- Keep the quota cap on the key (`MASTERPLAN.md` §24.2)
