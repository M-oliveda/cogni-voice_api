# SPDX-License-Identifier: GPL-2.0-or-later
#
# Service accounts and least-privilege bindings (MASTERPLAN.md §13.3). Mirrors
# infra/scripts/create_service_accounts.sh and grant_runtime_roles.sh.

resource "google_service_account" "runtime" {
  account_id   = "cognivoice-runtime"
  display_name = "CogniVoice API runtime (Cloud Run)"
}

resource "google_service_account" "tasks_invoker" {
  account_id   = "cognivoice-tasks-invoker"
  display_name = "CogniVoice Cloud Tasks OIDC invoker"
}

resource "google_cloud_tasks_queue_iam_member" "runtime_enqueuer" {
  name     = google_cloud_tasks_queue.interactions.name
  location = google_cloud_tasks_queue.interactions.location
  role     = "roles/cloudtasks.enqueuer"
  member   = google_service_account.runtime.member
}

resource "google_service_account_iam_member" "runtime_acts_as_invoker" {
  service_account_id = google_service_account.tasks_invoker.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.runtime.member
}

resource "google_service_account_iam_member" "deployer_acts_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.deployer_service_account}"
}

# The API is public; tenant authentication happens in the application.
resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
