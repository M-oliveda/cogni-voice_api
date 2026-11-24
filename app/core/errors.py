# SPDX-License-Identifier: GPL-2.0-or-later
"""Error envelope and global exception handlers (MASTERPLAN.md §4.3).

Every failure is returned as::

    {"error": {"code": "...", "message": "...", "details": {...},
               "request_id": "..."}}

``code`` is a stable, lowercase snake_case identifier that clients may rely on;
``message`` is human-readable and may change.
"""

import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, ClassVar

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)


class ErrorBody(BaseModel):
    """The body of the error envelope."""

    code: str = Field(examples=["not_found"])
    message: str = Field(examples=["The requested resource was not found."])
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = Field(
        default=None, examples=["5f0c2d7e-2c1b-4f6e-9a39-1d2b8a6c4e10"]
    )


class ErrorResponse(BaseModel):
    """The error envelope returned by every failing request."""

    error: ErrorBody


class AppError(Exception):
    """Base class of the errors the API turns into an envelope.

    Subclasses set ``code`` and ``status_code``; instances may override the
    message and add ``details``.
    """

    code: ClassVar[str] = "internal_error"
    status_code: ClassVar[int] = HTTPStatus.INTERNAL_SERVER_ERROR
    default_message: ClassVar[str] = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Create the error.

        Args:
            message: Human-readable message; defaults to the class message.
            details: Extra machine-readable information for the client.
        """
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)


class BadRequestError(AppError):
    """The request is malformed or semantically invalid."""

    code = "bad_request"
    status_code = HTTPStatus.BAD_REQUEST
    default_message = "The request is invalid."


class AuthenticationError(AppError):
    """Credentials are missing or invalid."""

    code = "unauthenticated"
    status_code = HTTPStatus.UNAUTHORIZED
    default_message = "Authentication is required."


class PermissionDeniedError(AppError):
    """The caller is authenticated but not allowed to do this."""

    code = "permission_denied"
    status_code = HTTPStatus.FORBIDDEN
    default_message = "You do not have permission to perform this action."


class NotFoundError(AppError):
    """The resource does not exist or is not visible to the caller."""

    code = "not_found"
    status_code = HTTPStatus.NOT_FOUND
    default_message = "The requested resource was not found."


class ConflictError(AppError):
    """The request conflicts with the current state of the resource."""

    code = "conflict"
    status_code = HTTPStatus.CONFLICT
    default_message = "The request conflicts with the current state."


class DatabaseUnavailableError(AppError):
    """The database cannot be reached or did not answer in time."""

    code = "database_unavailable"
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    default_message = "The database is temporarily unavailable."


class AIProviderError(AppError):
    """The AI provider failed or is unavailable."""

    code = "ai_provider_unavailable"
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    default_message = "The AI provider is temporarily unavailable."


# Codes for HTTP errors raised by the framework (unknown route, wrong method).
_HTTP_STATUS_CODES: dict[int, str] = {
    HTTPStatus.BAD_REQUEST: BadRequestError.code,
    HTTPStatus.UNAUTHORIZED: AuthenticationError.code,
    HTTPStatus.FORBIDDEN: PermissionDeniedError.code,
    HTTPStatus.NOT_FOUND: NotFoundError.code,
    HTTPStatus.METHOD_NOT_ALLOWED: "method_not_allowed",
    HTTPStatus.CONFLICT: ConflictError.code,
    HTTPStatus.UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build an error envelope response.

    Args:
        status_code: HTTP status of the response.
        code: Stable error code.
        message: Human-readable message.
        details: Extra machine-readable information.
        headers: Extra response headers.

    Returns:
        The JSON response.
    """
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=details or {},
            request_id=get_request_id(),
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(body),
        headers=headers,
    )


async def _handle_app_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, AppError)
    if error.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        logger.warning(
            "Request failed: %s",
            error.code,
            extra={"error_code": error.code},
        )
    return error_response(error.status_code, error.code, error.message, error.details)


async def _handle_validation_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)
    # Only the location, message and type: never echo the submitted input.
    errors = [
        {
            "loc": list(item.get("loc", ())),
            "msg": item.get("msg", ""),
            "type": item.get("type", ""),
        }
        for item in error.errors()
    ]
    return error_response(
        HTTPStatus.UNPROCESSABLE_CONTENT,
        "validation_error",
        "The request failed validation.",
        {"errors": errors},
    )


async def _handle_http_exception(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, StarletteHTTPException)
    status = HTTPStatus(error.status_code)
    code = _HTTP_STATUS_CODES.get(status, status.phrase.lower().replace(" ", "_"))
    message = error.detail if isinstance(error.detail, str) else status.phrase
    return error_response(status, code, message, headers=error.headers)


async def _handle_database_error(_: Request, error: Exception) -> JSONResponse:
    logger.error(
        "Database unavailable: %s",
        type(error).__name__,
        extra={"error_code": DatabaseUnavailableError.code},
    )
    return error_response(
        DatabaseUnavailableError.status_code,
        DatabaseUnavailableError.code,
        DatabaseUnavailableError.default_message,
    )


def unexpected_error_response(error: Exception) -> JSONResponse:
    """Log an unhandled exception and build the generic 500 envelope.

    Called by the request middleware, which sits inside Starlette's outermost
    error middleware, so the response still carries the request ID.

    Args:
        error: The unhandled exception.

    Returns:
        The ``internal_error`` response.
    """
    # The type only: exception messages may contain user data.
    logger.error(
        "Unhandled error: %s",
        type(error).__name__,
        extra={"error_code": AppError.code},
    )
    return error_response(
        HTTPStatus.INTERNAL_SERVER_ERROR, AppError.code, AppError.default_message
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Install the handlers that turn every failure into the envelope.

    Unhandled exceptions are turned into the envelope by the request
    middleware (:func:`unexpected_error_response`).

    Args:
        app: The application.
    """
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    for database_error in (OperationalError, DBAPIError, PoolTimeoutError):
        app.add_exception_handler(database_error, _handle_database_error)


# Documented on every operation: the envelope for the errors any route can return.
# A plain dict because FastAPI's ``responses`` parameter takes one.
# pylint: disable-next=consider-using-namedtuple-or-dataclass
COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    HTTPStatus.UNPROCESSABLE_CONTENT: {
        "model": ErrorResponse,
        "description": "Validation error",
    },
    HTTPStatus.INTERNAL_SERVER_ERROR: {
        "model": ErrorResponse,
        "description": "Unexpected error",
    },
    HTTPStatus.SERVICE_UNAVAILABLE: {
        "model": ErrorResponse,
        "description": "A dependency is temporarily unavailable",
    },
}
