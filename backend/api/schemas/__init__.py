"""Typed request and response models.

Every model forbids unknown fields, so a caller who sends something the API does
not understand gets a 422 instead of having it silently dropped. That matters
most for detection, where a dropped field could have been an attack label.
"""

from backend.api.schemas.common import ApiErrorResponse, ApiModel

__all__ = ["ApiModel", "ApiErrorResponse"]
