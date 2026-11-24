# SPDX-License-Identifier: GPL-2.0-or-later

output "service_url" {
  description = "Deterministic Cloud Run URL, also used as the Cloud Tasks OIDC audience (SERVICE_URL)."
  value       = local.service_url
}

output "runtime_service_account" {
  description = "Identity of the Cloud Run service and migration job."
  value       = google_service_account.runtime.email
}

output "tasks_invoker_service_account" {
  description = "OIDC identity attached to Cloud Tasks requests."
  value       = google_service_account.tasks_invoker.email
}
