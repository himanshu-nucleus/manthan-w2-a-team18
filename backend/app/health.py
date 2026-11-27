"""Liveness and readiness endpoints.

Two separate checks, because they answer different questions:

* ``/health``        - is the process up? No dependencies touched. Use this for
                       the container HEALTHCHECK and for uptime alerting.
* ``/health/ready``  - can it actually serve traffic? Touches the database.
                       Use this before sending load, and as the panel that goes
                       red first during the SRE drill.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness - is the API process up (public, ops only)")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Return 200 whenever the process is running. Never touches the database."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }


@router.get(
    "/health/ready",
    summary="Readiness - 200 if the database answers, 503 if not (public, ops only)",
    responses={503: {"description": "Database unreachable; body is `{status, database}`."}},
)
def readiness(response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    """Return 200 when the database answers, 503 when it does not.

    Returning 503 rather than raising keeps the body shape stable, so a
    dashboard or an alert rule can parse the same JSON either way.
    """
    try:
        db.execute(text("select 1"))
    except Exception as exc:
        logger.warning("Readiness check failed: %s", exc)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "database": "unavailable"}

    return {"status": "ready", "database": "ok"}
