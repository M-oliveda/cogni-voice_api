#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Enables the Google APIs CogniVoice needs in one environment project.
# Enabling an already enabled API is a no-op. Usage: enable_apis.sh dev|stg|prod

set -euo pipefail
# shellcheck source=infra/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_environment "${1:-}"

readonly APIS=(
  run.googleapis.com
  cloudtasks.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  sts.googleapis.com
  storage.googleapis.com
)

log "enabling ${APIS[*]} in ${PROJECT_ID}"
run gcloud services enable "${APIS[@]}" --project="$PROJECT_ID"
