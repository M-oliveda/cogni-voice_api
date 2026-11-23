# CogniVoice API

![License: GPL-2.0-only](https://img.shields.io/badge/license-GPL--2.0--only-blue.svg)
![Python 3.14](https://img.shields.io/badge/python-3.14-3776AB.svg)
![Status: planning](<https://img.shields.io/badge/status-planning%20(phase%200)-lightgrey.svg>)

**CogniVoice** (Cognitive Voice of the Customer) is a B2B, API-first platform for customer-feedback intelligence. Companies push raw customer text (emails, chat transcripts, app reviews, support tickets, social comments) to a multi-tenant REST API. CogniVoice masks personal data, analyzes each item with an LLM (sentiment, emotion, topics, summary), stores a semantic embedding, and exposes the results through analytics endpoints, semantic search, and an **AI agent** that answers natural-language questions about a tenant's feedback by calling those capabilities as tools.

The service follows a **"payloads, not files"** philosophy: it only handles UTF-8 text, JSON, and vectors (max 1,000 characters per item). Tenant isolation is enforced twice: in the application layer and with PostgreSQL Row Level Security (RLS).

> **Project status:** the architecture, roadmap, and quality gates are defined in [`MASTERPLAN.md`](MASTERPLAN.md). Commands and endpoints in this README describe the target setup and become available as each roadmap phase lands.

## Table of Contents

- [CogniVoice API](#cognivoice-api)
  - [Table of Contents](#table-of-contents)
  - [Primary Tools and Technologies](#primary-tools-and-technologies)
  - [Architecture at a Glance](#architecture-at-a-glance)
  - [Getting Started and CLI Instructions](#getting-started-and-cli-instructions)
    - [Prerequisites](#prerequisites)
    - [First-time setup](#first-time-setup)
    - [Daily development workflow](#daily-development-workflow)
    - [Make targets](#make-targets)
    - [Dependencies](#dependencies)
    - [Other useful commands](#other-useful-commands)
  - [Docker Operations](#docker-operations)
  - [Environment Variables](#environment-variables)
  - [API Documentation](#api-documentation)
  - [Testing and Quality Gates](#testing-and-quality-gates)
  - [Contributing](#contributing)
  - [Project Documentation](#project-documentation)
  - [License](#license)

## Primary Tools and Technologies

| Area                   | Choice                                                                                                                                                     |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Language / runtime     | Python 3.14                                                                                                                                                |
| API framework          | FastAPI (async), Pydantic v2, `pydantic-settings`; versioned REST under `/api/v1`                                                                          |
| ORM / migrations       | SQLAlchemy 2.x (async, `asyncpg`), Alembic, `pgvector`                                                                                                     |
| Database / auth        | Supabase: PostgreSQL + pgvector + Supabase Auth (JWT)                                                                                                      |
| AI orchestration       | LangGraph (ReAct-style agent) with LangChain chat and embedding integrations                                                                               |
| AI providers           | Gemini via Google AI Studio (cloud) · Ollama (local only) · deterministic `fake` provider (tests)                                                          |
| Queue                  | Google Cloud Tasks (cloud) · database-polling worker (local), behind one `TaskQueue` interface                                                             |
| Compute and cloud      | Google Cloud Run, Google Cloud Tasks                                                                                                                       |
| Registry / secrets     | Docker Hub (images) · GitHub Secrets (secrets and tokens)                                                                                                  |
| Observability          | Python `logging` (structured JSON on stdout), Cloud Run console metrics, optional OpenTelemetry                                                            |
| LLM data format        | TOON (Token-Oriented Object Notation, `toon-format` package) for data sent to the LLM; Pydantic for validation                                             |
| Infrastructure as code | Terraform (format and validation only, never applied) plus `gcloud` setup scripts                                                                          |
| CI/CD                  | GitHub Actions with Workload Identity Federation (keyless GCP authentication)                                                                              |
| Containers             | Docker (one multi-stage `Dockerfile`), one Docker Compose file (local only) that also runs the Supabase services                                           |
| Code quality           | Black, isort, flake8, pylint, mypy (strict), Bandit, pip-audit, gitleaks, `pre-commit`                                                                     |
| Testing                | pytest, pytest-asyncio, pytest-cov (100% branch coverage gate), httpx, Testcontainers, Hypothesis, respx, DeepEval (agent evaluation), Locust (load tests) |
| Dependencies           | `pip` + `pip-tools` (`requirements.in` → pinned `requirements.txt` / `requirements-dev.txt`)                                                               |
| Task runner            | `Makefile`                                                                                                                                                 |
| Demo UI                | Single HTML page styled with Tailwind CSS (CDN, demo only)                                                                                                 |

## Architecture at a Glance

```text
Route (api/v1)  →  Service (business logic)  →  Repository (SQLAlchemy)  →  Postgres (RLS)
                        ↓
                AI providers / TaskQueue / Agent tools
```

- **Ingestion is asynchronous.** `POST /api/v1/ingest/interactions` validates, masks PII, stores the item as `pending`, enqueues a task, and returns `202 Accepted`. Cloud Tasks (or the local worker) then runs analysis and embedding through the same `ProcessInteractionService`.
- **Roles:** Super Admin, Tenant Admin, Tenant Viewer (Supabase JWT) and Machine (API key with scopes). The Super Admin manages tenants but **cannot read tenant feedback content**.
- **The AI agent** uses four read-only tools over the same services as the REST API. The tenant is never a tool argument; it comes from the authenticated request.
- **Environments:** `local`, `development`, `staging` and `production`. Locally, one `docker-compose.yaml` starts Supabase, the API, and the worker together.
- **LLM data format:** data placed in prompts and returned by agent tools is encoded in [TOON](https://github.com/toon-format/toon) to save tokens; model output is still validated with Pydantic.
- **Demo:** the read-only `/demo` page is enabled in every environment by default so external people can try the app.

See [`MASTERPLAN.md`](MASTERPLAN.md) §4 to §10 for the full design.

## Getting Started and CLI Instructions

### Prerequisites

- Python **3.14** (see `.python-version`)
- [Docker](https://docs.docker.com/get-docker/) with Docker Compose v2
- [Ollama](https://ollama.com/) installed natively on the host (local AI; not needed if you use a Gemini key)
- `make`, `git`, and (for infrastructure work) Terraform and the `gcloud` CLI

### First-time setup

```bash
git clone <repository-url> cognivoice_api
cd cognivoice_api

cp .env.example .env          # then edit the values (see "Environment Variables")
make setup                    # creates .venv, installs pinned dependencies, installs git hooks
```

Pull the local models once (Ollama runs on the host, not in Docker):

```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

### Daily development workflow

```bash
docker compose up --build     # Supabase (Postgres + pgvector + Auth), API, and worker together
make migrate                  # apply Alembic migrations
make seed                     # optional: synthetic demo tenant (~150-200 interactions)
```

The API runs with hot reload at <http://localhost:8000>. To run the API or the worker outside Docker instead (for example under a debugger), start only the Supabase services with `docker compose up -d --scale api=0 --scale worker=0` and then run `make run` and, in a second terminal, `make worker`.

Create the first Super Admin for the environment:

```bash
python scripts/create_super_admin.py
```

### Make targets

| Target           | Description                                                                                         |
| ---------------- | --------------------------------------------------------------------------------------------------- |
| `make setup`     | Create `.venv`, install dependencies, install pre-commit/commit-msg/pre-push hooks                  |
| `make format`    | Run Black and isort                                                                                 |
| `make lint`      | Run flake8, pylint, and Bandit                                                                      |
| `make typecheck` | Run mypy in strict mode                                                                             |
| `make test-unit` | Fast unit tests only                                                                                |
| `make test`      | Full suite (unit, integration, RLS, contract, agent, E2E) with the 100% coverage gate; needs Docker |
| `make cov`       | Generate the combined branch-coverage report                                                        |
| `make run`       | Run the API locally with reload                                                                     |
| `make worker`    | Run the local DB-polling worker                                                                     |
| `make migrate`   | Apply Alembic migrations                                                                            |
| `make seed`      | Seed the demo tenant                                                                                |
| `make load-test` | Run the Locust load-test scenarios (on demand)                                                      |
| `make licenses`  | Check dependency licences against the GPL-2.0-only allowlist                                        |

### Dependencies

Edit `requirements.in`, then recompile the pinned files with `pip-compile` and commit them (`requirements-dev.txt` is compiled the same way for development and test tooling):

```bash
pip-compile --generate-hashes requirements.in
```

### Other useful commands

```bash
python scripts/re_embed.py        # re-embed after changing the embedding model
python scripts/smoke_test.py      # post-deploy smoke test against a running environment
pre-commit run --all-files        # run every hook locally, as CI does
```

## Docker Operations

Docker Compose is used for **local development only**. The single `docker-compose.yaml` runs **all** local services: the Supabase services (Postgres with pgvector, Auth, API gateway), the `api`, and the `worker` (Dockerfile target `dev`, bind mounts, hot reload), so the app and Supabase start and run together. Ollama runs natively on the host; containers reach it at `host.docker.internal:11434`. Deployed environments run on Cloud Run from the `prod` image target, published to Docker Hub.

```bash
docker compose up --build                 # build images and start all services
docker compose up -d                      # start in the background
docker compose restart <service>          # restart one service, e.g. api or worker
docker compose down                       # stop and remove the containers
docker compose exec <service> <command>   # run a command inside a service
```

Examples:

```bash
docker compose exec api alembic upgrade head   # run migrations
docker compose exec api pytest tests/unit      # run unit tests
docker compose exec api bash                   # open a shell
docker compose logs -f worker                  # follow worker logs
```

Build the deployable image locally:

```bash
docker build --target prod -t cognivoice-api:local .
```

## Environment Variables

Local values live in `.env` (git-ignored); `.env.example` is committed with placeholders. Variable names are uppercase. In the cloud, secrets come from **GitHub Secrets** (injected into Cloud Run as environment variables at deploy time) and non-secrets from GitHub Environment variables and Cloud Run settings. No Google Cloud Secret Manager is used. **Never commit real values.**

| Variable                    | Secret | Description                                                                   | Example / default           |
| --------------------------- | :----: | ----------------------------------------------------------------------------- | --------------------------- |
| `APP_ENV`                   |   no   | `local`, `development`, `staging`, or `production`                            | `local`                     |
| `LOG_LEVEL`                 |   no   | Log verbosity                                                                 | `INFO`                      |
| `DOCS_ENABLED`              |   no   | Expose Swagger UI, ReDoc, and `/openapi.json`                                 | `true`                      |
| `CORS_ALLOWED_ORIGINS`      |   no   | Comma-separated allowlist of origins                                          | `http://localhost:3000`     |
| `DATABASE_URL`              |  yes   | Application connection (`cognivoice_app` role; pooler URL in the cloud)       | `postgresql+asyncpg://...`  |
| `DATABASE_MIGRATION_URL`    |  yes   | Alembic connection (admin role), used only by the migration job               | `postgresql+asyncpg://...`  |
| `DB_POOL_SIZE`              |   no   | Connections kept per instance                                                 | `5`                         |
| `DB_POOL_MAX_OVERFLOW`      |   no   | Extra connections allowed under load                                          | `5`                         |
| `DB_POOL_TIMEOUT`           |   no   | Seconds to wait for a pooled connection                                       | `10`                        |
| `DB_ECHO`                   |   no   | Log SQL statements (local debugging only)                                     | `false`                     |
| `SUPABASE_URL`              |   no   | Supabase project URL                                                          | `http://127.0.0.1:54321`    |
| `SUPABASE_JWT_SECRET`       |  yes   | JWT verification secret (or configure the JWKS URL)                           | _(from Supabase)_           |
| `SUPABASE_SERVICE_ROLE_KEY` |  yes   | Server-side key used to invite users; never exposed to clients                | _(from Supabase)_           |
| `API_KEY_HMAC_SECRET`       |  yes   | Secret for keyed hashing (HMAC-SHA256) of API keys                            | _(random, 32+ bytes)_       |
| `AI_PROVIDER`               |   no   | `gemini`, `ollama`, or `fake` (`fake` only allowed in `local`)                | `ollama`                    |
| `GEMINI_API_KEY`            |  yes   | Google AI Studio key (use a **paid** key for real customer data)              | _(from AI Studio)_          |
| `GEMINI_MODEL`              |   no   | Gemini chat model                                                             | `gemini-2.5-flash-lite`     |
| `GEMINI_EMBEDDING_MODEL`    |   no   | Gemini embedding model                                                        | `gemini-embedding-001`      |
| `OLLAMA_BASE_URL`           |   no   | Ollama endpoint                                                               | `http://localhost:11434`    |
| `OLLAMA_MODEL`              |   no   | Local chat model                                                              | `llama3.2:3b`               |
| `OLLAMA_EMBEDDING_MODEL`    |   no   | Local embedding model                                                         | `nomic-embed-text`          |
| `EMBEDDING_DIMENSIONS`      |   no   | Vector size stored in pgvector                                                | `768`                       |
| `MAX_INTERACTION_CHARS`     |   no   | Maximum characters per ingested item                                          | `1000`                      |
| `TASK_QUEUE_BACKEND`        |   no   | `db` (local worker) or `cloud_tasks`                                          | `db`                        |
| `GCP_PROJECT_ID`            |   no   | Google Cloud project                                                          | _(cloud only)_              |
| `GCP_REGION`                |   no   | Google Cloud region                                                           | `us-central1`               |
| `CLOUD_TASKS_QUEUE`         |   no   | Cloud Tasks queue name                                                        | _(cloud only)_              |
| `CLOUD_TASKS_INVOKER_SA`    |   no   | Service account whose OIDC token Cloud Tasks attaches                         | _(cloud only)_              |
| `SERVICE_URL`               |   no   | Cloud Run service URL, used as the OIDC audience                              | _(cloud only)_              |
| `AGENT_MAX_STEPS`           |   no   | Maximum reasoning/tool steps per agent run                                    | `6` (Gemini), `4` (Ollama)  |
| `AGENT_MAX_TOKENS`          |   no   | Token budget per agent run                                                    | `8000`                      |
| `AGENT_TIMEOUT_SECONDS`     |   no   | Wall-clock timeout per agent run                                              | `60`                        |
| `AGENT_RETENTION_DAYS`      |   no   | Retention for agent threads and checkpoints                                   | `90`                        |
| `AUDIT_RETENTION_DAYS`      |   no   | Retention for the `agent_runs` audit trail                                    | `365`                       |
| `TRACING_ENABLED`           |   no   | Export OpenTelemetry traces (optional)                                        | `false`                     |
| `DEMO_ENABLED`              |   no   | Serve `/demo` (enabled by default in every environment, including production) | `true`                      |
| `DEMO_TENANT_ID`            |   no   | Tenant used (read-only) by the demo page                                      | _(UUID of the demo tenant)_ |

GitHub Environments (`development`, `staging`, `production`) store non-secret configuration as variables (`GCP_PROJECT_ID`, `GCP_REGION`, `WIF_PROVIDER`, `DEPLOY_SERVICE_ACCOUNT`) and the runtime secrets as GitHub Secrets (`DATABASE_URL`, `GEMINI_API_KEY`, and the other secret variables above). The Docker Hub credentials (`DOCKERHUB_USERNAME` variable and `DOCKERHUB_TOKEN` secret) are repository-level GitHub values and are not application settings. There are no long-lived GCP keys: GitHub authenticates through Workload Identity Federation.

## API Documentation

When the API is running (and `DOCS_ENABLED=true`):

| URL                                        | Description                                           |
| ------------------------------------------ | ----------------------------------------------------- |
| `http://localhost:8000/docs`               | Swagger UI                                            |
| `http://localhost:8000/redoc`              | ReDoc                                                 |
| `http://localhost:8000/openapi.json`       | OpenAPI schema                                        |
| `http://localhost:8000/demo`               | Interactive demo page (on by default; `DEMO_ENABLED`) |
| `http://localhost:8000/healthz`, `/readyz` | Liveness and readiness probes                         |

Authentication:

- **Humans:** sign in through Supabase Auth and send `Authorization: Bearer <JWT>`.
- **Machines:** send `X-API-Key: <key>`; keys look like `cvk_<env>_<prefix>_<secret>` and are shown only once at creation.

Example ingestion request:

```bash
curl -X POST http://localhost:8000/api/v1/ingest/interactions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $COGNIVOICE_API_KEY" \
  -d '{
        "source_type": "app_review",
        "text_content": "I love dark mode, but the app crashes every time I export a PDF.",
        "language": "en",
        "external_id": "review-8821",
        "metadata": { "app_version": "2.1.4", "platform": "iOS" }
      }'
```

The response is `202 Accepted` with an `interaction_id` and a `status_url` to poll. Re-sending the same `external_id` returns the existing record (`200`). Only `application/json` is accepted.

## Testing and Quality Gates

Development is **test-first**: every change ships with its tests, and merges and deployments are blocked below **100% merged line and branch coverage**.

| Layer                 | Location            | Purpose                                                               |
| --------------------- | ------------------- | --------------------------------------------------------------------- |
| Unit                  | `tests/unit`        | Pure logic (PII masking, hashing, guardrails, configuration)          |
| Integration           | `tests/integration` | Repositories, services, migrations, routes, provider adapters         |
| RLS isolation         | `tests/rls`         | Tenant A can never read or search tenant B's data                     |
| Contract              | `tests/contract`    | OpenAPI snapshot to catch breaking changes                            |
| Agent (deterministic) | `tests/agent`       | Graph, guardrails, tool arguments, trajectories (scripted fake model) |
| E2E                   | `tests/e2e`         | Real HTTP journeys against the running stack with the `fake` provider |
| Agent evaluation      | `tests/evals`       | LLM-judged quality with DeepEval (nightly and on demand)              |
| Load                  | `tests/load`        | Locust scenarios (on demand, never against production)                |

The local `pre-commit` framework blocks confidential files and runs fast checks on commit (formatting and linting of staged files, strict mypy on the whole project), validates the Gitmoji commit message, and runs the tests related to your unpushed commits on push (the full suite when the branch has no upstream yet). **CI re-runs every check and enforces the full suite and the 100% coverage gate**, so `--no-verify` cannot get untested code merged.

## Contributing

- **Branching:** GitFlow (`main`, `develop`, `feature/*`, `release/*`, `hotfix/*`). Releases follow Semantic Versioning.
- **Commits:** Gitmoji format `:emoji: Message`, where the message starts with an uppercase letter, has no trailing period, and the first line is at most 72 characters (see [gitmoji.dev](https://gitmoji.dev)). Git-generated `Merge`, `Revert`, `fixup!`, `squash!`, and `amend!` messages are accepted. Examples:
  - `:sparkles: Add user authentication`
  - `:bug: Fix token validation issue`
  - `:memo: Update README with setup instructions`
- **Code standards:** Black (88 columns), isort, flake8, pylint, strict mypy, type hints on all functions, Google-style docstrings, `Optional[X]` for optional types, absolute imports.
- **Architecture rules:** route → service → repository; tenant scoping plus RLS; never bypass RLS; the tenant is never an LLM tool argument; data sent to the LLM is encoded in TOON (the REST API stays JSON); PII masking is mandatory; never log interaction text, prompts, or secrets; secrets live in GitHub Secrets and the git-ignored `.env`.
- **Infrastructure:** Terraform is only formatted and validated (`terraform fmt`, `terraform validate`), never applied; cloud environments are set up with the scripts in `infra/scripts/` and the CI/CD pipelines.
- **Migrations:** applied migrations are never edited; use backward-compatible expand/contract changes.
- **Licensing:** the project is GPL-2.0-only. New source files carry `SPDX-License-Identifier: GPL-2.0-only`, and new dependencies must be GPLv2-compatible.
- **AI assistants:** `AGENTS.md` is the single source of rules; `CLAUDE.md` is a symlink to it.

Every pull request targets `develop` (or `main` for hotfixes) and must pass the full CI gate.

## Project Documentation

| Document                         | Content                                                                |
| -------------------------------- | ---------------------------------------------------------------------- |
| [`MASTERPLAN.md`](MASTERPLAN.md) | Architecture, data model, API, pipeline, security, operations, roadmap |
| `AGENTS.md` / `CLAUDE.md`        | Rules for AI coding assistants                                         |
| `docs/architecture.md`           | Architecture diagrams                                                  |
| `docs/cloud-tasks.md`            | Queue behaviour, retries, local worker parity                          |
| `docs/agent.md`                  | Agent graph, tools, guardrails                                         |
| `docs/testing.md`                | Test layers, coverage policy, evaluations                              |
| `docs/performance.md`            | Performance targets and load-test results                              |
| `docs/privacy.md`                | Data retention, erasure, sub-processors                                |
| `docs/runbooks/`                 | Operational runbooks, incident response, disaster recovery             |
| `docs/adr/`                      | Architecture Decision Records                                          |

## License

This project is licensed under the **GNU General Public License, version 2 only** (`GPL-2.0-only`). See the [`LICENSE`](LICENSE) file for the full text.

Copyright (C) the CogniVoice contributors.

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License version 2 as published by the Free Software Foundation. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
