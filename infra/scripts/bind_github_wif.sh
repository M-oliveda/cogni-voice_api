#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Lets GitHub Actions runs of this repository impersonate the existing
# deployer service account through the existing Workload Identity pool
# (MASTERPLAN.md §13.1). The pool, provider, and deployer are reused, never
# created here. Adding an existing IAM binding is a no-op.
# Usage: bind_github_wif.sh dev|stg|prod

set -euo pipefail
# shellcheck source=infra/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_environment "${1:-}"

if ! exists gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER_ID" \
  --workload-identity-pool="$WIF_POOL" --location=global --project="$PROJECT_ID"; then
  echo "missing ${WIF_PROVIDER}; it must already exist (MASTERPLAN.md §2, decision 15)" >&2
  exit 1
fi
if ! exists gcloud iam service-accounts describe "$DEPLOYER_SA" --project="$PROJECT_ID"; then
  echo "missing ${DEPLOYER_SA}; it must already exist (MASTERPLAN.md §2, decision 15)" >&2
  exit 1
fi

member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/attribute.repository/${REPOSITORY}"
log "granting workloadIdentityUser on ${DEPLOYER_SA} to ${REPOSITORY}"
run gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" \
  --project="$PROJECT_ID" \
  --role=roles/iam.workloadIdentityUser \
  --member="$member" \
  --condition=None \
  --quiet >/dev/null
