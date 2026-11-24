# SPDX-License-Identifier: GPL-2.0-or-later
#
# Developer commands. Targets for later phases (run, worker, migrate, seed,
# load-test) are added as those phases land (MASTERPLAN.md §25).

PYTHON ?= python3.14
VENV := .venv
BIN := $(VENV)/bin
SRC := app scripts tests

# Runtime licences compatible with GPL-2.0-or-later (MASTERPLAN.md §26). Matched
# as substrings of the licence names pip-licenses reports.
LICENSE_ALLOWLIST := MIT;BSD;ISC;Apache;PSF;Python Software Foundation;MPL-2.0;Mozilla Public License 2.0;LGPL;GNU Lesser General Public License;GPL-2.0-or-later;GPLv2+;GPL-3.0;GPLv3;Unlicense;CC0

.DEFAULT_GOAL := help
.PHONY: help setup env format lint typecheck test-unit test cov licenses

help: ## Show the available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-12s %s\n", $$1, $$2}'

setup: ## Create .venv, install pinned dependencies, install git hooks
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --quiet --upgrade pip pip-tools
	$(BIN)/pip-sync requirements.txt requirements-dev.txt
	$(BIN)/pre-commit install

env: ## Create .env from .env.example with new local secrets
	$(BIN)/python scripts/generate_local_env.py

format: ## Run Black and isort
	$(BIN)/black $(SRC)
	$(BIN)/isort $(SRC)

lint: ## Run flake8, pylint, and Bandit
	$(BIN)/flake8 $(SRC)
	$(BIN)/pylint $(SRC)
	$(BIN)/bandit -q -c pyproject.toml -r app scripts

typecheck: ## Run mypy in strict mode
	$(BIN)/mypy

test-unit: ## Run the fast unit tests (no coverage gate)
	$(BIN)/pytest -m unit --no-cov

test: ## Run the full suite with the 100% coverage gate
	$(BIN)/pytest

cov: ## Run the full suite and write htmlcov/ and coverage.xml
	$(BIN)/pytest --cov-report=html --cov-report=xml

licenses: ## Check runtime dependency licences against the allowlist
	$(BIN)/pip-licenses --from=mixed --partial-match \
		--allow-only="$(LICENSE_ALLOWLIST)" \
		--packages $$(grep -oE '^[A-Za-z0-9][A-Za-z0-9._-]*' requirements.txt)
