<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Disaster recovery

Source: `MASTERPLAN.md` §21. Everything runs on free tiers (decision 31): the single Supabase project has daily backups but **no point-in-time recovery**, so the practical RPO is up to 24 hours plus the latest logical export.

## Symptoms

- The Supabase project is lost, corrupted, or unrecoverably paused
- A GCP project or the Cloud Run service is deleted

## Impact

Every environment is down, because all three share the database.

## Diagnosis

1. Check the Supabase dashboard (project status, backups).
2. Check `gcloud run services list --project=$PROJECT --region=us-central1`.
3. Run `infra/scripts/verify_environment.sh <env>` for each environment.

## Remediation

1. **Declare** the incident and freeze deploys in all environments ([incident response](incident-response.md)).
2. **Restore** the database from the latest Supabase backup, or from the newest export in `gs://moliveda-gcloudprojects-prod-cognivoice-backups`, into a new free project if needed.
3. **Give the role its login:** `infra/scripts/configure_database_role.sh` (see README).
4. **Repoint** the repository secrets (`DATABASE_URL`, `DATABASE_MIGRATION_URL`, `SUPABASE_*`) with `gh secret set` and `gh variable set SUPABASE_URL`.
5. **Rebuild cloud resources** with `infra/scripts/setup_environment.sh <env>` if a project lost them.
6. **Redeploy** development (it runs the migrations), then staging and production.
7. **Reconcile the queue** once Phase 5 exists: requeue `pending` and stale `processing` rows.

## Verification

- `alembic current` matches the head revision; the `cognivoice_app` role, RLS policies, and `FORCE ROW LEVEL SECURITY` are intact
- `make smoke URL=<service URL>` passes in every environment

## Prevention

- Quarterly restore drill into a scratch free project (§21.5)
- Keep the backup bucket's versioning and lifecycle rule (`infra/scripts/create_backup_bucket.sh`)
