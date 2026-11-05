"""Consistent API errors.

Every failure leaves the API as the same JSON envelope::

    {
      "error": {
        "code": "NOT_FOUND",
        "message": "no session with id ...",
        "details": {...},
        "request_id": "..."
      }
    }

so a client never has to parse a framework-specific body, and a reported failure
can always be tied back to a log line by its correlation identifier.

An unhandled exception is logged with its traceback and answered with a generic
message: the traceback never reaches the client.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, Mapping, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.context import (
    REQUEST_ID_HEADER,
    current_request_id,
    request_id_for,
)

logger = logging.getLogger("sih26141.api")


class ErrorCode(str, Enum):
    """Machine-readable error identifiers."""

    BAD_REQUEST = "BAD_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    UNPROCESSABLE_ENTITY = "UNPROCESSABLE_ENTITY"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


_STATUS_FOR_CODE: Mapping[ErrorCode, int] = {
    ErrorCode.BAD_REQUEST: status.HTTP_400_BAD_REQUEST,
    ErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.CONFLICT: status.HTTP_409_CONFLICT,
    ErrorCode.PAYLOAD_TOO_LARGE: status.HTTP_413_CONTENT_TOO_LARGE,
    ErrorCode.UNPROCESSABLE_ENTITY: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.SERVICE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
}

_CODE_FOR_STATUS: Mapping[int, ErrorCode] = {
    code: error for error, code in _STATUS_FOR_CODE.items()
}


def code_for_status(status_code: int) -> ErrorCode:
    """Return the error code for an HTTP status, by exact match then by family."""
    exact = _CODE_FOR_STATUS.get(status_code)
    if exact is not None:
        return exact
    if 400 <= status_code < 500:
        return ErrorCode.BAD_REQUEST
    return ErrorCode.INTERNAL_ERROR


class ApiError(Exception):
    """An error the API raises deliberately and can describe to a client."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: Optional[Mapping[str, Any]] = None,
        status_code: Optional[int] = None,
    ) -> None:
        self.code = code if isinstance(code, ErrorCode) else ErrorCode(code)
        self.message = str(message)
        self.details: Dict[str, Any] = dict(details) if details else {}
        self.status_code = (
            int(status_code) if status_code is not None else _STATUS_FOR_CODE[self.code]
        )
        super().__init__(f"{self.code.value}: {self.message}")


def not_found(what: str, identifier: str) -> ApiError:
    """Return a 404 for a missing resource."""
    return ApiError(
        ErrorCode.NOT_FOUND,
        f"no {what} with id {identifier!r}",
        details={"resource": what, "id": identifier},
    )


def conflict(message: str, **details: Any) -> ApiError:
    """Return a 409 for an invalid lifecycle transition."""
    return ApiError(ErrorCode.CONFLICT, message, details=details)


def error_envelope(
    code: ErrorCode,
    message: str,
    *,
    details: Optional[Mapping[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the error body. Single definition, used by every handler."""
    payload: Dict[str, Any] = {
        "code": code.value if isinstance(code, ErrorCode) else str(code),
        "message": str(message),
        "request_id": request_id if request_id is not None else current_request_id(),
    }
    if details:
        payload["details"] = dict(details)
    return {"error": payload}


def error_response(
    status_code: int,
    code: ErrorCode,
    message: str,
    *,
    details: Optional[Mapping[str, Any]] = None,
    headers: Optional[Mapping[str, str]] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Build a JSON error response, tagged with the correlation identifier.

    ``request_id`` is normally read from the request context. It is passed
    explicitly by the unhandled-exception handler, which runs above the
    middleware that binds it.
    """
    request_id = request_id or current_request_id()
    response = JSONResponse(
        status_code=status_code,
        content=error_envelope(code, message, details=details, request_id=request_id),
    )
    if request_id:
        response.headers[REQUEST_ID_HEADER] = request_id
    for key, value in (headers or {}).items():
        response.headers[key] = value
    return response


def _jsonable_validation_errors(errors: Any) -> list:
    """Return pydantic errors with every value reduced to JSON-safe data.

    ``RequestValidationError.errors()`` can carry exception objects in ``ctx``,
    which would make the response unserialisable.
    """
    safe = []
    for item in errors or []:
        if not isinstance(item, Mapping):
            safe.append({"message": str(item)})
            continue
        entry: Dict[str, Any] = {
            "loc": [str(part) for part in item.get("loc", ())],
            "msg": str(item.get("msg", "")),
            "type": str(item.get("type", "")),
        }
        context = item.get("ctx")
        if isinstance(context, Mapping):
            entry["ctx"] = {str(k): str(v) for k, v in context.items()}
        safe.append(entry)
    return safe


def register_error_handlers(app: FastAPI) -> None:
    """Attach the error handlers that make the envelope universal."""

    @app.exception_handler(ApiError)
    async def _handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, details=exc.details)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ErrorCode.UNPROCESSABLE_ENTITY,
            "request validation failed",
            details={"errors": _jsonable_validation_errors(exc.errors())},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return error_response(
            int(exc.status_code),
            code_for_status(int(exc.status_code)),
            str(exc.detail),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:



        request_id = current_request_id() or request_id_for(request.scope)
        logger.exception(
            "unhandled API error",
            extra={"request_id": request_id, "error_type": type(exc).__name__},
        )
        return error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            ErrorCode.INTERNAL_ERROR,
            "internal server error; the failure was logged against the request id",
            request_id=request_id,
        )
