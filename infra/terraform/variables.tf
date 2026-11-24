# SPDX-License-Identifier: GPL-2.0-or-later

variable "project_id" {
  description = "GCP project of the environment (moliveda-gcloudprojects-<env>)."
  type        = string
}

variable "region" {
  description = "Region of every CogniVoice resource."
  type        = string
  default     = "us-central1"
}

variable "app_env" {
  description = "APP_ENV of the deployed application."
  type        = string

  validation {
    condition     = contains(["development", "staging", "production"], var.app_env)
    error_message = "app_env must be development, staging, or production."
  }
}

variable "deployer_service_account" {
  description = "Existing CI/CD deployer service account (reused, not managed here)."
  type        = string
}

variable "image" {
  description = "Image reference pinned by digest (docker.io/<user>/cognivoice-api@sha256:...)."
  type        = string
}

variable "max_instances" {
  description = "Cloud Run max-instances cost guardrail (2 in dev and stg, 5 in prod)."
  type        = number
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "cognivoice-api"
}
