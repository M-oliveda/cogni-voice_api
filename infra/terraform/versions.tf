# SPDX-License-Identifier: GPL-2.0-or-later
#
# Terraform showcase of the CogniVoice target architecture (MASTERPLAN.md §13.3,
# decision 16). It is ONLY formatted and validated (`terraform fmt -check`,
# `terraform init -backend=false`, `terraform validate`). It has no backend,
# no state, and no credentials, and `terraform plan` / `terraform apply` are
# never run: the real environments are configured by infra/scripts/ and the
# deploy workflows, because the GCP projects also host unrelated resources.

terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.12"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
