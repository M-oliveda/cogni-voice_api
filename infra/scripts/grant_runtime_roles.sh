#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Least-privilege IAM for CogniVoice (MASTERPLAN.md §13.3). Grants are scoped
# to the queue and the service accounts, never the project, so the other
# workloads in these projects are unaffected. The deployer's existing roles
# are shared with other repositories and are not changed. Adding an existing
# binding is a no-op. Usage: grant_runtime_roles.sh dev|stg|prod

set -euo pipefail
# shellcheck source=infra/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_environment "${1:-}"

log "runtime may enqueue tasks on ${QUEUE_NAME}"
run gcloud tasks queues add-iam-policy-binding "$QUEUE_NAME" \
  --location="$REGION" --project="$PROJECT_ID" \
  --role=roles/cloudtasks.enqueuer \
  --member="serviceAccount:${RUNTIME_SA}" >/dev/null

log "runtime may sign task OIDC tokens as ${INVOKER_SA}"
run gcloud iam service-accounts add-iam-policy-binding "$INVOKER_SA" \
  --project="$PROJECT_ID" \
  --role=roles/iam.serviceAccountUser \
  --member="serviceAccount:${RUNTIME_SA}" \
  --condition=None --quiet >/dev/null

log "deployer may deploy revisions and jobs as ${RUNTIME_SA}"
run gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --project="$PROJECT_ID" \
  --role=roles/iam.serviceAccountUser \
  --member="serviceAccount:${DEPLOYER_SA}" \
  --condition=None --quiet >/dev/null
