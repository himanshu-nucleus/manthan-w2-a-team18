"""Aggregate router for the versioned API.

Every feature router is included here, and this is the only place that happens.
Mounted by ``create_app()`` under the prefix from settings (``/api/v1``).

Adding a feature::

    # app/api/<feature>.py
    from fastapi import APIRouter
    router = APIRouter(prefix="/<feature>", tags=["<feature>"])

    # then here
    from app.api import <feature>
    api_router.include_router(<feature>.router)

Keep domain logic out of this file - it is wiring only.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import auth, claims, users

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(claims.router)
