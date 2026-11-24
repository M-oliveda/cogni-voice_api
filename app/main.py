# SPDX-License-Identifier: GPL-2.0-or-later
"""Application factory (MASTERPLAN.md §4, §11).

Run with ``uvicorn app.main:create_app --factory``.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Final

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import health
from app.api.docs import ApiVersion, register_docs
from app.api.v1 import API_V1
from app.api.v1 import router as api_v1_router
from app.core.config import AppEnv, Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.db.engine import create_engine, create_sessionmaker
from app.dependencies.state import AppState

API_TITLE: Final = "CogniVoice API"
API_DESCRIPTION: Final = """
Multi-tenant, API-first customer-feedback intelligence.

Push raw customer text; CogniVoice masks personal data, analyses it with an
LLM, stores a semantic embedding, and exposes analytics, semantic search, and
an AI agent over the results.

* **Errors** always use the envelope
  `{"error": {"code", "message", "details", "request_id"}}`; `code` is stable.
* **Correlation:** send `X-Request-ID` or read the generated one from every
  response.
* **Compatibility:** responses may gain fields within a major version.
"""

# Served major versions, oldest first; the root docs redirect to the last.
API_VERSIONS: Final[tuple[ApiVersion, ...]] = (API_V1,)

OPENAPI_TAGS: Final = [
    {"name": "health", "description": "Liveness and readiness probes."},
]

# Public base URL per environment, shown in the OpenAPI `servers` list.
SERVER_URLS: Final = {
    AppEnv.LOCAL: "http://localhost:8000",
}


def _servers(settings: Settings) -> list[dict[str, str]]:
    url = settings.service_url or SERVER_URLS.get(settings.app_env)
    if url is None:
        return []
    return [{"url": url, "description": settings.app_env.value}]


def _lifespan(settings: Settings) -> Any:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        app.state.cognivoice = AppState(
            settings=settings,
            engine=engine,
            sessionmaker=create_sessionmaker(engine),
        )
        try:
            yield
        finally:
            await engine.dispose()

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application.

    Args:
        settings: Settings to use; read from the environment when omitted.

    Returns:
        The configured application.
    """
    settings = settings or get_settings()
    configure_logging(settings)
    app = FastAPI(
        title=API_TITLE,
        version=__version__,
        description=API_DESCRIPTION,
        contact={
            "name": "CogniVoice",
            "url": "https://github.com/M-oliveda/cogni-voice_api",
        },
        license_info={
            "name": "GPL-2.0-or-later",
            "identifier": "GPL-2.0-or-later",
        },
        openapi_tags=OPENAPI_TAGS,
        servers=_servers(settings),
        # Each version serves its own docs (app/api/docs.py).
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
        swagger_ui_parameters={"persistAuthorization": True},
        lifespan=_lifespan(settings),
    )
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    # Added last, so it wraps CORS and sees every response.
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    app.include_router(api_v1_router)
    if settings.docs_enabled:
        register_docs(app, API_VERSIONS)
    return app
