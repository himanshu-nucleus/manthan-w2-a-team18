"""Per-request context (client IP, request id) for the audit trail.

The request id comes from an ``X-Request-ID`` header when it is a sane value, otherwise
it is generated; either way it is echoed back in the response header, so a user can
quote it and finance can find the matching audit rows. The IP is the direct peer
address; proxy headers are not trusted.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from fastapi import FastAPI, Request, Response

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
client_ip_var: ContextVar[str | None] = ContextVar("client_ip", default=None)
request_path_var: ContextVar[str | None] = ContextVar("request_path", default=None)


def register_request_context(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        id_token = request_id_var.set(request_id)
        ip_token = client_ip_var.set(request.client.host if request.client else None)
        path_token = request_path_var.set(f"{request.method} {request.url.path}")
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(id_token)
            client_ip_var.reset(ip_token)
            request_path_var.reset(path_token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
