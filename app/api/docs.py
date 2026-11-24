# SPDX-License-Identifier: GPL-2.0-or-later
"""Per-version API documentation (MASTERPLAN.md §7.8, §13).

One application serves every major version, but each version gets its own
OpenAPI schema, Swagger UI, and ReDoc under its prefix (``/api/v1/docs``). A
version's schema holds its own operations plus the unversioned system routes
(``/healthz``, ``/readyz``); the root ``/docs`` and ``/redoc`` redirect to the
latest version.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

VERSIONED_PATH_PREFIX: Final = "/api/"


@dataclass(frozen=True)
class ApiVersion:
    """A major version of the public API.

    Attributes:
        major: The major version number.
        prefix: The path prefix its routes are mounted under.
    """

    major: int
    prefix: str

    @property
    def openapi_url(self) -> str:
        """The path of this version's OpenAPI schema."""
        return f"{self.prefix}/openapi.json"

    @property
    def docs_url(self) -> str:
        """The path of this version's Swagger UI."""
        return f"{self.prefix}/docs"

    @property
    def redoc_url(self) -> str:
        """The path of this version's ReDoc."""
        return f"{self.prefix}/redoc"

    def documents(self, path: str) -> bool:
        """Tell whether a route path belongs in this version's schema.

        Args:
            path: The route path.

        Returns:
            True for this version's routes and the unversioned system routes.
        """
        return path.startswith(f"{self.prefix}/") or not path.startswith(
            VERSIONED_PATH_PREFIX
        )


def build_openapi(app: FastAPI, version: ApiVersion) -> dict[str, Any]:
    """Build the OpenAPI schema of one API version.

    Args:
        app: The application.
        version: The version to document.

    Returns:
        The schema, titled with the major version and carrying the app version.
    """
    return get_openapi(
        title=f"{app.title} v{version.major}",
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=[
            route
            for route in app.routes
            if version.documents(getattr(route, "path", ""))
        ],
        tags=app.openapi_tags,
        servers=app.servers,
        contact=app.contact,
        license_info=app.license_info,
        separate_input_output_schemas=app.separate_input_output_schemas,
    )


def _root_path(request: Request) -> str:
    root_path: str = request.scope.get("root_path", "")
    return root_path.rstrip("/")


def _register_version(app: FastAPI, version: ApiVersion) -> None:
    schema: dict[str, Any] = {}
    title = f"{app.title} v{version.major}"

    async def openapi(_: Request) -> JSONResponse:
        if not schema:
            schema.update(build_openapi(app, version))
        return JSONResponse(schema)

    async def swagger_ui(request: Request) -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url=_root_path(request) + version.openapi_url,
            title=f"{title} - Swagger UI",
            swagger_ui_parameters=app.swagger_ui_parameters,
        )

    async def redoc(request: Request) -> HTMLResponse:
        return get_redoc_html(
            openapi_url=_root_path(request) + version.openapi_url,
            title=f"{title} - ReDoc",
        )

    app.add_route(version.openapi_url, openapi, include_in_schema=False)
    app.add_route(version.docs_url, swagger_ui, include_in_schema=False)
    app.add_route(version.redoc_url, redoc, include_in_schema=False)


def _register_redirect(app: FastAPI, path: str, target: str) -> None:
    async def redirect(request: Request) -> RedirectResponse:
        return RedirectResponse(_root_path(request) + target)

    app.add_route(path, redirect, include_in_schema=False)


def register_docs(app: FastAPI, versions: Sequence[ApiVersion]) -> None:
    """Serve each version's schema and docs, and redirect the root docs.

    Args:
        app: The application, created with its built-in docs disabled.
        versions: The served versions, oldest first; the last is the latest.
    """
    for version in versions:
        _register_version(app, version)
    latest = versions[-1]
    _register_redirect(app, "/docs", latest.docs_url)
    _register_redirect(app, "/redoc", latest.redoc_url)
