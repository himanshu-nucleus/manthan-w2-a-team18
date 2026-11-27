"""Prometheus metrics and request logging.

Exposes ``GET /metrics`` in the text format Prometheus scrapes, plus three
metrics that are enough to build the SRE dashboard and one alert:

* ``http_requests_total``            - counter by method, path template, status
* ``http_request_duration_seconds``  - histogram by method and path template
* ``http_requests_in_progress``      - gauge of concurrent requests

Labelling uses the **route template** (``/api/v1/items/{item_id}``) rather than
the raw path, so high-cardinality ids do not explode the metric series.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.routing import Match

logger = logging.getLogger(__name__)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests.",
    ["method", "path", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
    # Buckets tuned for a web API: sub-second detail, a tail above 1s.
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being served.",
    ["method"],
)


def _route_template(request: Request) -> str:
    """Return the matched route template, or 'unmatched' for unknown paths.

    Using the raw URL path here would create a new metric series per id and
    make the dashboard unusable within minutes.
    """
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match is Match.FULL:
            return getattr(route, "path", request.url.path)
    return "unmatched"


def register_observability(app: FastAPI) -> None:
    """Attach the metrics middleware and the /metrics endpoint."""

    @app.middleware("http")
    async def record_metrics(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        started = time.perf_counter()
        IN_PROGRESS.labels(method=method).inc()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - started
            path = _route_template(request)
            IN_PROGRESS.labels(method=method).dec()
            REQUEST_COUNT.labels(method=method, path=path, status=str(status_code)).inc()
            REQUEST_LATENCY.labels(method=method, path=path).observe(elapsed)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
