#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Configures one cloud environment end to end by running every setup script
# in dependency order, then verifies it (MASTERPLAN.md §13.3). Safe to re-run.
# Usage: [DRY_RUN=1] setup_environment.sh dev|stg|prod

set -euo pipefail
here="$(dirname "${BASH_SOURCE[0]}")"
# shellcheck source=infra/scripts/lib.sh
source "$here/lib.sh"
load_environment "${1:-}"

"$here/enable_apis.sh" "$ENV_NAME"
"$here/bind_github_wif.sh" "$ENV_NAME"
"$here/create_service_accounts.sh" "$ENV_NAME"
"$here/setup_cloud_tasks.sh" "$ENV_NAME"
"$here/grant_runtime_roles.sh" "$ENV_NAME"
"$here/create_backup_bucket.sh" "$ENV_NAME"

if [[ "${DRY_RUN:-0}" != "1" ]]; then
  "$here/verify_environment.sh" "$ENV_NAME"
fi
