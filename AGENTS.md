# AGENTS.md

Rules for AI coding assistants working on **CogniVoice API**. This file is the single source of rules; `CLAUDE.md` is a symlink to it. Keep it concise and update it in the same pull request whenever architecture, commands, or conventions change. [`MASTERPLAN.md`](MASTERPLAN.md) holds the full design; read the relevant section before changing behaviour.

## 1. Project summary

CogniVoice is a B2B, API-first, multi-tenant platform for customer-feedback intelligence: it ingests raw text, masks PII, analyzes it with an LLM, stores embeddings, and exposes analytics, semantic search, and a LangGraph agent. Stack: Python 3.14, FastAPI, SQLAlchemy 2.x async, Alembic, Supabase (Postgres, pgvector, Auth), Gemini (cloud) and Ollama (local). Status: planning; commands below become available as the roadmap phases land (`MASTERPLAN.md` §25).

## 2. Setup and daily commands

```bash
make setup      # create .venv, install pinned dependencies, install git hooks
make format     # Black and isort
make lint       # flake8, pylint, Bandit
make typecheck  # mypy (strict)
make test-unit  # fast unit tests
make test       # full suite with the 100% coverage gate (needs Docker)
make cov        # full suite plus htmlcov/ and coverage.xml
make licenses   # runtime dependency licences against the allowlist
make run        # API with hot reload
make worker     # local queue worker
make migrate    # apply Alembic migrations
make seed       # seed the demo tenant

docker compose up --build   # Supabase + api + worker, all local services together
```

## 3. Architecture rules

- Layering is **route → service → repository → Postgres (RLS)**. Routes hold no business logic; only repositories contain SQL.
- Tenant isolation is enforced twice: tenant-scoped repositories **and** Row Level Security. Never bypass or disable RLS; there is no super-admin bypass on content tables.
- **The tenant is never an LLM tool argument.** It comes from the authenticated request context.
- Depend on abstractions: `LLMProvider`, `EmbeddingProvider`, and `TaskQueue` (Cloud Tasks in the cloud, DB-polling worker locally). Both paths call the same `ProcessInteractionService`.
- **Data sent to the LLM** (prompt data, agent tool results) is encoded in **TOON** through `app/ai/toon.py` (the `toon-format` package), not JSON. See <https://github.com/toon-format/toon>. Model output is still validated with Pydantic, and the REST API stays JSON.
- PII masking is mandatory before storage or any LLM call. Input is capped at 1,000 characters.
- REST API is versioned under `/api/v1`; every error uses the envelope `{"error": {"code", "message", "details", "request_id"}}`.

## 4. Code standards

- Python 3.14 is a hard requirement; never downgrade it to fix a dependency.
- Black (88 columns), isort, flake8, pylint, mypy strict, Bandit.
- Type hints on all functions; use `Optional[X]` for optional types; Google-style docstrings; absolute imports; custom exception classes.
- Logging uses the standard `logging` module with structured JSON on stdout. Never log interaction text, prompts, agent questions or answers, API keys, JWTs, connection strings, or secrets.
- Dependencies: edit `requirements.in` (runtime) or `requirements-dev.in` (tooling), then recompile with `pip-compile --generate-hashes` (see README "Dependencies").

## 5. Testing rules

- Test-first: every change ships with its tests, and merged line and branch coverage must stay at **100%**.
- Unit, integration, and E2E tests use the `fake` AI provider and never call the network. Real models are used only in `tests/evals/` and post-deploy smoke tests.
- Every new tenant table needs RLS tests proving tenant A cannot read tenant B's data.
- `# pragma: no cover` only with a written justification.

## 6. Security and secrets

- No secrets in code, logs, images, or Git. Locally use the git-ignored `.env` (names in capitals; document every variable in `.env.example` and the README).
- In CI and the cloud, secrets live in **GitHub Secrets**. Google Secret Manager is **not** used.
- Never commit `design/`, `.env*` (except `.env.example`), `*.pem`, or `*.key`; the pre-commit hook blocks them and `git add -f` must not be used to bypass it.
- gitleaks runs in hooks and CI.

## 7. Git workflow

- GitFlow: `main`, `develop`, `feature/<topic>`, `release/<n>`, `hotfix/<topic>`; Semantic Versioning.
- Commit messages use **Gitmoji**: `:<shortcode>: <Capitalised message>`, no trailing period, first line at most 72 characters (for example `:sparkles: Add semantic search endpoint`). Reference: <https://gitmoji.dev>.
- Hooks use the Python `pre-commit` framework (pre-commit, commit-msg, and pre-push stages). Never use `--no-verify` and never force-push shared branches. CI re-runs every check.
- Pull requests target `develop` (or `main` for hotfixes) and must pass the full CI gate.

## 8. Docker, cloud, and infrastructure

- One multi-stage `Dockerfile` (`base`, `builder`, `dev`, `prod`) and **one** `docker-compose.yaml`, used only locally. It runs the Supabase services, `api`, and `worker` together. Ollama runs natively on the Mac host (`host.docker.internal:11434`).
- Cloud Run runs the `prod` image, published to **Docker Hub** (not Artifact Registry). Authentication to GCP uses Workload Identity Federation; no service-account keys.
- The three GCP projects already contain other resources and the service accounts (`cicd-deployer-*`) and WIF pool (`github-pool`) already exist. Check them with `gcloud`; do not recreate them.
- **Terraform is only formatted and validated** (`terraform fmt`, `terraform validate`). Never run `terraform apply`. Cloud setup is done with the scripts in `infra/scripts/` and the CI/CD pipelines.
- The demo (`/demo`) is enabled in every environment by default (`DEMO_ENABLED=true`); it is read-only and pinned to the demo tenant.

## 9. Boundaries

- Do not add out-of-scope features (webhooks, quotas, rate limiting, billing) in v1.
- Applied migrations are immutable; fix forward with a new migration. Migrations follow expand/contract and ship their RLS policies in the same migration.
- Breaking API changes need a new major version and the deprecation process (`MASTERPLAN.md` §7.8).
- The project is **GPL-2.0-or-later**: new files carry `SPDX-License-Identifier: GPL-2.0-or-later`, and new runtime dependencies must have licences compatible with it (`make licenses`; allowlist in the `Makefile`).
- Keep `README.md`, `AGENTS.md`, and `MASTERPLAN.md` current when architecture, commands, or conventions change.

## 10. Agent workflow

- **Plan before medium or complex changes.** A change is medium or complex when it touches several files or layers, adds a dependency, changes a migration, the public API, security, or architecture, or its approach is not obvious. Enter a planning phase first: write a coding plan (goal, affected files, approach, tests, risks) and get the user's approval before editing code. Trivial, single-file fixes may proceed directly.
- **No commits, pushes, or pull requests without explicit authorization.** Do not run `git commit`, `git push`, or create or update pull requests unless the user explicitly asks for that specific action. Approval for one commit, push, or pull request does not extend to later ones.
- **No new documentation files unless asked.** Do not create Markdown or other documentation files (ADRs, change logs, summaries, reports, notes about what an agent did) unless the user explicitly requests them. Keep only the documentation needed to set up and run the application: `README.md`, `AGENTS.md` (with its `CLAUDE.md` symlink), `MASTERPLAN.md`, and `.env.example`. Record decisions by updating those files, and report work in the conversation instead of in files.
