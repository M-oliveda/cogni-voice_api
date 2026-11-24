# SPDX-License-Identifier: GPL-2.0-or-later
#
# Interaction-processing queue with the starting values of MASTERPLAN.md §8.3.
# Mirrors infra/scripts/setup_cloud_tasks.sh.

resource "google_cloud_tasks_queue" "interactions" {
  name     = "cognivoice-interactions"
  location = var.region

  rate_limits {
    max_dispatches_per_second = 2
    max_concurrent_dispatches = 5
  }

  retry_config {
    max_attempts = 5
    min_backoff  = "10s"
    max_backoff  = "300s"
  }
}
