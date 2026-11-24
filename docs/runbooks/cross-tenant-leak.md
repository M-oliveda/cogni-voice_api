<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Suspected cross-tenant leak

**Default severity:** SEV1 (see [incident response](incident-response.md)). Source: `MASTERPLAN.md` §22.1.

## Symptoms

- A report or a test shows one tenant seeing another tenant's data

## Impact

Confidential customer data may be exposed. This is always SEV1.

## Diagnosis

Set the environment first: `PROJECT=moliveda-gcloudprojects-<dev|stg|prod>`, `REGION=us-central1`, `SERVICE=cognivoice-api`, `QUEUE=cognivoice-interactions`.

1. Preserve logs before anything else (export the relevant Cloud Run log range)
2. Run the RLS suite against the affected database
3. Identify the route, repository, and policy involved

## Remediation

1. Disable the affected route (or set `DEMO_ENABLED=false` if the demo is involved) and redeploy
2. Fix with a test that reproduces the leak; never disable RLS
3. Follow [incident response](incident-response.md), including notification

## Verification

- The RLS suite passes against the environment
- The reproduction test passes

## Prevention

- Every tenant table keeps its RLS policy test (`MASTERPLAN.md` §13.5)
