"""Consistent error envelope for all API error responses.

Per DESIGN_DOCUMENT.md Section 5.6 and Appendix B, every error response uses
the shape ``{"error": {"code", "message", "details"}}``. This module wires
that envelope onto FastAPI's three error paths: explicit ``HTTPException``s
raised by route handlers, Pydantic request-validation failures, and any
uncaught exception (which becomes a 500).
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

# fastapi.HTTPException is a subclass of starlette's; registering the handler
# for the Starlette base class (below, in main.py) catches both — routes
# raised via `from fastapi import HTTPException` and any raw Starlette 404s
# for unmatched routes.

_STATUS_TO_CODE: dict[int, str] = {
    400: "invalid_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    500: "internal_error",
}


def _code_for_status(status_code: int) -> str:
    return _STATUS_TO_CODE.get(status_code, "unknown_error")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


async def http_exception_to_envelope(request: Request, exc: Exception) -> JSONResponse:
    """Convert an HTTPException (401/404/409/etc.) into the error envelope.

    ``exc.detail`` is either a plain string, or a dict like
    ``{"message": "...", "errors": [...]}`` (see tickets.py's CSV import
    validation). In the dict case, `message` is pulled out and everything
    else is preserved under `details`.

    Typed as ``Exception`` (not ``HTTPException``) because Starlette's
    ``add_exception_handler`` requires handlers to accept the exception base
    class; this is only ever registered for and invoked with ``HTTPException``.
    """
    assert isinstance(exc, HTTPException)
    detail = exc.detail
    if isinstance(detail, dict):
        message = str(detail.get("message", "request failed"))
        details = {k: v for k, v in detail.items() if k != "message"} or None
    else:
        message = str(detail)
        details = None

    envelope = ErrorEnvelope(
        error=ErrorDetail(code=_code_for_status(exc.status_code), message=message, details=details)
    )
    return JSONResponse(status_code=exc.status_code, content=jsonable_encoder(envelope.model_dump()))


async def validation_exception_to_envelope(request: Request, exc: Exception) -> JSONResponse:
    """Convert a Pydantic request-validation failure into the error envelope.

    Typed as ``Exception`` for the same Starlette-signature reason as
    ``http_exception_to_envelope`` above; only ever registered for and
    invoked with ``RequestValidationError``.
    """
    assert isinstance(exc, RequestValidationError)
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code=_code_for_status(422),
            message="request validation failed",
            details={"errors": jsonable_encoder(exc.errors())},
        )
    )
    return JSONResponse(status_code=422, content=envelope.model_dump())


async def unhandled_exception_to_envelope(request: Request, exc: Exception) -> JSONResponse:
    """Convert any uncaught exception into a generic 500 error envelope.

    Never leaks internal exception details to the client; the exception
    should already have been logged upstream (e.g. via structlog) before
    this handler is reached.
    """
    envelope = ErrorEnvelope(
        error=ErrorDetail(code=_code_for_status(500), message="internal server error", details=None)
    )
    return JSONResponse(status_code=500, content=envelope.model_dump())
