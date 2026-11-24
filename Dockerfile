# syntax=docker/dockerfile:1
# SPDX-License-Identifier: GPL-2.0-or-later
#
# One multi-stage image (MASTERPLAN.md §13.4), selected with --target:
#   base     Python runtime, non-root user
#   builder  pinned runtime dependencies in a virtual environment
#   dev      adds development and test tooling; Compose bind-mounts the source
#   prod     minimal runtime deployed to Cloud Run and used for migrations
#
# The base image is pinned by digest and refreshed monthly by Dependabot.
ARG PYTHON_IMAGE=python:3.14-slim@sha256:22eafb370920ad8b429e0aec3fff433e0669968519f5d60469d83729c138b28b

FROM ${PYTHON_IMAGE} AS base
LABEL org.opencontainers.image.title="cognivoice-api" \
      org.opencontainers.image.source="https://github.com/M-oliveda/cogni-voice_api" \
      org.opencontainers.image.licenses="GPL-2.0-or-later"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home app
WORKDIR /app

FROM base AS builder
RUN python -m venv "$VIRTUAL_ENV"
COPY requirements.txt ./
RUN pip install --require-hashes -r requirements.txt

FROM builder AS dev
COPY requirements-dev.txt ./
RUN pip install --require-hashes -r requirements-dev.txt
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS prod
COPY --from=builder /opt/venv /opt/venv
# Source stays owned by root so the runtime user cannot modify it.
COPY app/ ./app/
USER app
# Cloud Run sends traffic to port 8080 by default.
EXPOSE 8080
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
