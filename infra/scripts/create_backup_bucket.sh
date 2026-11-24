#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Creates the versioned logical-export bucket (MASTERPLAN.md §21.2): uniform
# access, public access prevention, and a lifecycle rule that deletes
# noncurrent versions after 30 days and objects after 90 days, which keeps it
# inside the Cloud Storage free tier. Usage: create_backup_bucket.sh dev|stg|prod

set -euo pipefail
# shellcheck source=infra/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_environment "${1:-}"

if exists gcloud storage buckets describe "$BACKUP_BUCKET" --project="$PROJECT_ID"; then
  log "bucket ${BACKUP_BUCKET} already exists"
else
  log "creating bucket ${BACKUP_BUCKET}"
  run gcloud storage buckets create "$BACKUP_BUCKET" \
    --project="$PROJECT_ID" --location="$REGION" \
    --uniform-bucket-level-access --public-access-prevention
fi

lifecycle="$(mktemp)"
trap 'rm -f "$lifecycle"' EXIT
cat >"$lifecycle" <<'JSON'
{
  "rule": [
    {"action": {"type": "Delete"}, "condition": {"daysSinceNoncurrentTime": 30}},
    {"action": {"type": "Delete"}, "condition": {"age": 90}}
  ]
}
JSON

log "enabling versioning and the lifecycle rule on ${BACKUP_BUCKET}"
run gcloud storage buckets update "$BACKUP_BUCKET" \
  --project="$PROJECT_ID" --versioning --lifecycle-file="$lifecycle"
