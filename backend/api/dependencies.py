"""Dependency providers.

The application object owns the settings and the store, and routes obtain them
through these providers rather than importing module-level singletons. That is
what lets a test build an application with its own settings and its own store
without touching global state.

Configured request bodies
-------------------------
Input bounds are configuration, not constants. A request model therefore cannot
carry its limits in a class body: the class is created once, while the settings
belong to the application instance. :func:`configured_body` closes that gap by
validating the parsed body a second time with the application's settings in the
Pydantic validation context, so the schema's own validators apply whatever limit
the running application was configured with.

Nothing global is involved. The schema class is shared; the limit arrives per
request from the application the request was routed to, so two applications in
one process cannot affect each other.
"""

from __future__ import annotations

from typing import Annotated, Callable, Type, TypeVar

from fastapi import Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from backend.api.config import ApiSettings
from backend.api.schemas.common import ApiModel
from backend.api.store import ApiStore

ModelT = TypeVar("ModelT", bound=ApiModel)


def get_settings(request: Request) -> ApiSettings:
    """Return the settings the application was built with."""
    return request.app.state.settings


def get_store(request: Request) -> ApiStore:
    """Return the application's orchestration store."""
    return request.app.state.store


def configured_body(schema: Type[ModelT]) -> Callable[..., ModelT]:
    """Build a dependency that validates ``schema`` against the active settings.

    The body is parsed once by FastAPI, which keeps the OpenAPI request contract,
    the ``extra="forbid"`` rule and the framework's own error shape exactly as
    they were. It is then re-validated with the settings in the context, which is
    the pass that applies the configured limits.

    Re-validating from ``model_dump()`` rather than from the parsed instance is
    deliberate. Validating an instance that has already passed its validators
    skips them on the second pass -- so a limit would never be applied -- whereas
    the dumped payload goes through every validator again exactly as the original
    request data did.

    Every annotation is assigned rather than written in the source, because this
    module uses ``from __future__ import annotations``: the annotations on a
    function defined here are stored as *strings*, and a string that refers to a
    name in this factory's closure cannot be resolved by FastAPI. Left as
    strings, ``body`` would be read as a query parameter and the configured pass
    would never run. Assigning the real objects (including ``Request`` and
    ``ApiSettings``) keeps the signature introspectable, keeps ``body`` a JSON
    body, and keeps the OpenAPI request schema intact.

    ``body`` is deliberately an ordinary required parameter in the signature, not
    one with a default. A defaulted body would make an absent or ``null`` payload
    resolve to ``None`` and raise inside this function -- a 500 for what is really
    a malformed request. Required keeps the framework's own 422.
    """

    def dependency(body, request, settings=Depends(get_settings)) -> ModelT:
        try:
            return schema.model_validate(
                body.model_dump(), context={"settings": settings}
            )
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from exc

    dependency.__annotations__ = {
        "body": schema,
        "request": Request,
        "settings": ApiSettings,
        "return": schema,
    }
    dependency.__name__ = f"configured_{schema.__name__}"
    return dependency


SettingsDep = Annotated[ApiSettings, Depends(get_settings)]
StoreDep = Annotated[ApiStore, Depends(get_store)]
