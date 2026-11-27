"""The error envelope, described for the OpenAPI contract.

Every error the API returns has this shape (see ``app/errors.py``). Routes list
the statuses they can return with ``error_responses(...)`` so the frontend sees
them in ``docs/openapi.json``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


_DESCRIPTIONS = {
    401: "Missing, invalid or expired token, or wrong credentials.",
    403: "Logged in, but the role is not allowed to do this.",
    404: "Not found.",
    409: "Conflicts with existing data.",
    422: "The request body or parameters are invalid.",
}


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI ``responses`` entries for the given error statuses."""
    return {
        code: {"model": ErrorResponse, "description": _DESCRIPTIONS[code]} for code in status_codes
    }
