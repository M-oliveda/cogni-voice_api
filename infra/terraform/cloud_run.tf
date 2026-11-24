# SPDX-License-Identifier: GPL-2.0-or-later
#
# The API service and the Alembic migration job, both from the same prod image
# (MASTERPLAN.md §13.2). Secrets are not modelled: the deploy workflow injects
# them from GitHub Secrets as environment variables (decision 28).

locals {
  service_url = "https://${var.service_name}-${data.google_project.this.number}.${var.region}.run.app"

  plain_env = {
    APP_ENV                = var.app_env
    AI_PROVIDER            = "gemini"
    TASK_QUEUE_BACKEND     = "cloud_tasks"
    GCP_PROJECT_ID         = var.project_id
    GCP_REGION             = var.region
    CLOUD_TASKS_QUEUE      = google_cloud_tasks_queue.interactions.name
    CLOUD_TASKS_INVOKER_SA = google_service_account.tasks_invoker.email
    SERVICE_URL            = local.service_url
  }
}

data "google_project" "this" {
  project_id = var.project_id
}

resource "google_cloud_run_v2_service" "api" {
  name                = var.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.runtime.email
    timeout         = "120s"

    scaling {
      min_instance_count = 0
      max_instance_count = var.max_instances
    }

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      dynamic "env" {
        for_each = local.plain_env
        content {
          name  = env.key
          value = env.value
        }
      }

      startup_probe {
        http_get {
          path = "/healthz"
        }
      }

      liveness_probe {
        http_get {
          path = "/healthz"
        }
      }
    }
  }
}

resource "google_cloud_run_v2_job" "migrate" {
  name                = "cognivoice-migrate"
  location            = var.region
  deletion_protection = false

  template {
    task_count = 1

    template {
      service_account = google_service_account.runtime.email
      max_retries     = 0
      timeout         = "600s"

      containers {
        image   = var.image
        command = ["alembic"]
        args    = ["upgrade", "head"]
      }
    }
  }
}
