<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Incident response

Source: `MASTERPLAN.md` §22.3. Failed deployments and nightly evaluations are reported by GitHub's default failure emails (§26).

| Severity | Definition | Target response |
| -------- | ---------- | --------------- |
| **SEV1** | Data exposure across tenants, data loss, or production fully down | Immediately |
| **SEV2** | Major feature unavailable or severe degradation; no data at risk | 1 hour |
| **SEV3** | Minor degradation or a workaround exists | Next business day |

1. **Detect and declare:** a manual check, a failed smoke test, or a report. Name an incident lead and start an incident note with timestamps.
2. **Stabilise first:** roll back the revision, disable the route, or pause the queue. Fix later.
3. **Communicate:** status to tenants for SEV1 and SEV2. A leaked secret also means rotating it (`gh secret set ...`, then redeploy) and reviewing access.
4. **Resolve and verify** with `make smoke URL=<service URL>` and the Cloud Run console.
5. **Review** within 5 business days with the [post-incident review template](post-incident-review-template.md).

Because one Supabase database serves every environment (decision 31), a database incident affects development, staging, and production together; freeze deploys in all three.
