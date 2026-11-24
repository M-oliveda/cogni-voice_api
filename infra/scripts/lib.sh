#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Shared helpers for the idempotent environment setup scripts
# (MASTERPLAN.md §13.3). Source it; do not run it. Every script takes the
# environment (dev, stg, or prod) as its first argument and supports
# DRY_RUN=1, which prints the mutating gcloud commands instead of running them.

# The constants are used by the scripts that source this file.
# shellcheck disable=SC2034

set -euo pipefail

# Never wait on an interactive gcloud prompt (for example "enable this API?").
export CLOUDSDK_CORE_DISABLE_PROMPTS=1

readonly REPOSITORY="M-oliveda/cogni-voice_api"
readonly REGION="us-central1"
readonly SERVICE_NAME="cognivoice-api"
readonly QUEUE_NAME="cognivoice-interactions"
readonly RUNTIME_SA_NAME="cognivoice-runtime"
readonly INVOKER_SA_NAME="cognivoice-tasks-invoker"
readonly WIF_POOL="github-pool"
readonly WIF_PROVIDER_ID="github-provider"

# Resolves ENV_NAME, PROJECT_ID, PROJECT_NUMBER, and the service-account
# emails for the environment given as $1.
load_environment() {
  ENV_NAME="${1:-}"
  case "$ENV_NAME" in
    dev) PROJECT_NUMBER="142167472193" ;;
    stg) PROJECT_NUMBER="454460555724" ;;
    prod) PROJECT_NUMBER="1034574533717" ;;
    *)
      echo "usage: $(basename "$0") dev|stg|prod" >&2
      exit 2
      ;;
  esac
  PROJECT_ID="moliveda-gcloudprojects-${ENV_NAME}"
  DEPLOYER_SA="cicd-deployer-${ENV_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
  RUNTIME_SA="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
  INVOKER_SA="${INVOKER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
  WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER_ID}"
  SERVICE_URL="https://${SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"
  BACKUP_BUCKET="gs://${PROJECT_ID}-cognivoice-backups"
  export ENV_NAME PROJECT_ID PROJECT_NUMBER DEPLOYER_SA RUNTIME_SA INVOKER_SA \
    WIF_PROVIDER SERVICE_URL BACKUP_BUCKET
}

log() {
  printf '[%s] %s\n' "${ENV_NAME:-?}" "$*"
}

# Runs a mutating command, or only prints it (on stderr) when DRY_RUN=1.
run() {
  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    {
      printf '[%s] dry-run:' "${ENV_NAME:-?}"
      printf ' %q' "$@"
      printf '\n'
    } >&2
  else
    "$@"
  fi
}

# Succeeds when the given read-only command succeeds; its output is discarded.
exists() {
  "$@" >/dev/null 2>&1
}
