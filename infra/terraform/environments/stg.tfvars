# SPDX-License-Identifier: GPL-2.0-or-later
# Example values for the showcase only; Terraform is never applied.
project_id               = "moliveda-gcloudprojects-stg"
app_env                  = "staging"
deployer_service_account = "cicd-deployer-stg@moliveda-gcloudprojects-stg.iam.gserviceaccount.com"
image                    = "docker.io/DOCKERHUB_USERNAME/cognivoice-api@sha256:0000000000000000000000000000000000000000000000000000000000000000"
max_instances            = 2
