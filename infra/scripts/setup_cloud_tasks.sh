#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Creates the interaction-processing queue, or brings an existing one back to
# the starting values of MASTERPLAN.md §8.3. Usage: setup_cloud_tasks.sh dev|stg|prod

set -euo pipefail
# shellcheck source=infra/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_environment "${1:-}"

readonly QUEUE_SETTINGS=(
  --max-attempts=5
  --min-backoff=10s
  --max-backoff=300s
  --max-concurrent-dispatches=5
  --max-dispatches-per-second=2
)

if exists gcloud tasks queues describe "$QUEUE_NAME" --location="$REGION" --project="$PROJECT_ID"; then
  log "updating queue ${QUEUE_NAME}"
  run gcloud tasks queues update "$QUEUE_NAME" \
    --location="$REGION" --project="$PROJECT_ID" "${QUEUE_SETTINGS[@]}"
else
  log "creating queue ${QUEUE_NAME}"
  run gcloud tasks queues create "$QUEUE_NAME" \
    --location="$REGION" --project="$PROJECT_ID" "${QUEUE_SETTINGS[@]}"
fi
