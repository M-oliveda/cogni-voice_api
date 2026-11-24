<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Agent timeouts or loops

**Default severity:** SEV3 (see [incident response](incident-response.md)). Source: `MASTERPLAN.md` §22.1.

> Applies once Phase 7 (AI agent) lands; until then this is a skeleton.

## Symptoms

- `agent_runs.status` is `timeout`
- Many step-limit hits

## Impact

Agent questions fail or return partial answers.

## Diagnosis

Set the environment first: `PROJECT=moliveda-gcloudprojects-<dev|stg|prod>`, `REGION=us-central1`, `SERVICE=cognivoice-api`, `QUEUE=cognivoice-interactions`.

1. Inspect `agent_runs.steps` for the failing runs
2. Check provider latency

## Remediation

1. Tighten `AGENT_MAX_STEPS`, `AGENT_MAX_TOKENS`, or `AGENT_TIMEOUT_SECONDS` through configuration and redeploy

## Verification

- New runs finish within the limits

## Prevention

- Add the trajectory to the deterministic agent tests
