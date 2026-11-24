#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Creates the Cloud Run runtime and the Cloud Tasks invoker service accounts
# when they are missing (MASTERPLAN.md §13.3). Existing accounts are left as
# they are. Usage: create_service_accounts.sh dev|stg|prod

set -euo pipefail
# shellcheck source=infra/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_environment "${1:-}"

ensure_service_account() {
  local name="$1" email="$2" display_name="$3"
  if exists gcloud iam service-accounts describe "$email" --project="$PROJECT_ID"; then
    log "service account ${email} already exists"
  else
    log "creating service account ${email}"
    run gcloud iam service-accounts create "$name" \
      --project="$PROJECT_ID" --display-name="$display_name"
  fi
}

ensure_service_account "$RUNTIME_SA_NAME" "$RUNTIME_SA" "CogniVoice API runtime (Cloud Run)"
ensure_service_account "$INVOKER_SA_NAME" "$INVOKER_SA" "CogniVoice Cloud Tasks OIDC invoker"
