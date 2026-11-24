<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Pull Request Template

## Summary

<!-- What changes and why. Link the roadmap item (MASTERPLAN.md §25) or issue. -->

## Checklist

- [ ] Tests ship with the change, and merged line and branch coverage stays at 100%
- [ ] `make format`, `make lint`, `make typecheck`, and `make test` pass locally
- [ ] Commit messages follow Gitmoji (`:<shortcode>: <Capitalised message>`)
- [ ] `README.md`, `AGENTS.md`, `MASTERPLAN.md`, and `.env.example` are updated if commands, conventions, or variables changed
- [ ] No secrets, interaction text, prompts, or tokens in code, logs, or fixtures
- [ ] New runtime dependencies pass `make licenses` (GPL-2.0-or-later compatible)

## Database migration review (MASTERPLAN.md §13.5)

<!-- Delete this section when the pull request has no migration. -->

- [ ] **Backward compatible:** the previous revision keeps working on the new schema (expand → migrate → contract)
- [ ] **Locks:** `lock_timeout` and `statement_timeout` are set; no long exclusive locks on hot tables
- [ ] **Indexes:** created `CONCURRENTLY` in a non-transactional migration; large HNSW builds are scheduled
- [ ] **RLS:** new tenant tables have `ENABLE` and `FORCE ROW LEVEL SECURITY`, policies, grants to `cognivoice_app`, and RLS tests
- [ ] **Backfill plan:** batched, resumable, and outside the schema transaction if needed
- [ ] **Rollback plan:** `downgrade` is tested (upgrade → downgrade → upgrade); destructive steps are marked
