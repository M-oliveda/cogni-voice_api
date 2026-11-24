#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Read-only check of one environment (MASTERPLAN.md §13.3): prints PASS or
# FAIL per prerequisite and exits non-zero when any check fails. It also
# prints the GitHub Environment variables the deploy workflow expects.
# Usage: verify_environment.sh dev|stg|prod

set -euo pipefail
# shellcheck source=infra/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_environment "${1:-}"

failures=0
check() {
  local description="$1"
  shift
  if exists "$@"; then
    printf 'PASS  %s\n' "$description"
  else
    printf 'FAIL  %s\n' "$description"
    failures=$((failures + 1))
  fi
}

api_enabled() {
  gcloud services list --enabled --project="$PROJECT_ID" \
    --filter="config.name=$1" --format="value(config.name)" | grep -q .
}

wif_bound() {
  gcloud iam service-accounts get-iam-policy "$DEPLOYER_SA" --project="$PROJECT_ID" \
    --format=json | grep -q "attribute.repository/${REPOSITORY}\""
}

for api in run cloudtasks iam iamcredentials sts storage; do
  check "API ${api}.googleapis.com enabled" api_enabled "${api}.googleapis.com"
done
check "WIF provider ${WIF_POOL}/${WIF_PROVIDER_ID}" \
  gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER_ID" \
  --workload-identity-pool="$WIF_POOL" --location=global --project="$PROJECT_ID"
check "deployer ${DEPLOYER_SA}" gcloud iam service-accounts describe "$DEPLOYER_SA" --project="$PROJECT_ID"
check "deployer trusts ${REPOSITORY}" wif_bound
check "runtime ${RUNTIME_SA}" gcloud iam service-accounts describe "$RUNTIME_SA" --project="$PROJECT_ID"
check "invoker ${INVOKER_SA}" gcloud iam service-accounts describe "$INVOKER_SA" --project="$PROJECT_ID"
check "queue ${QUEUE_NAME}" gcloud tasks queues describe "$QUEUE_NAME" --location="$REGION" --project="$PROJECT_ID"
check "bucket ${BACKUP_BUCKET}" gcloud storage buckets describe "$BACKUP_BUCKET" --project="$PROJECT_ID"

cat <<EOF

GitHub Environment variables for ${ENV_NAME}:
  GCP_PROJECT_ID=${PROJECT_ID}
  GCP_REGION=${REGION}
  WIF_PROVIDER=${WIF_PROVIDER}
  DEPLOY_SERVICE_ACCOUNT=${DEPLOYER_SA}
  RUNTIME_SERVICE_ACCOUNT=${RUNTIME_SA}
  CLOUD_TASKS_QUEUE=${QUEUE_NAME}
  CLOUD_TASKS_INVOKER_SA=${INVOKER_SA}
  SERVICE_URL=${SERVICE_URL}
EOF

if ((failures > 0)); then
  echo "${failures} check(s) failed" >&2
  exit 1
fi
