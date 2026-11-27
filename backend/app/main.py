"""Application factory and ASGI entrypoint.

    uvicorn app.main:app --reload

A factory (rather than a module-level app built inline) keeps tests honest:
every test gets a fresh application with its own dependency overrides.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.api.router import api_router
from app.config import Settings, get_settings
from app.errors import register_exception_handlers
from app.health import router as health_router
from app.observability import register_observability

logger = logging.getLogger(__name__)


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown.

    Deliberately does NOT create tables - schema changes go through Alembic so
    that migrations are reviewable and repeatable. Seeding is a separate script.
    """
    settings = get_settings()
    logger.info("Starting %s (%s)", settings.app_name, settings.environment)
    yield
    logger.info("Shutting down %s", settings.app_name)


API_DESCRIPTION = """
The single API contract for the frontend. The committed copy is `docs/openapi.json`.

**Auth:** `POST /api/v1/auth/login` returns `access_token`; send it on every other call as
`Authorization: Bearer <access_token>`. Dev login: `admin` / `admin` (finance_head).

**Roles:** `finance_head`, `employee`, `line_manager`, `finance_auditor`.

**Errors** always have the shape `{"error": {"code": "...", "message": "...", "details": {}}}`.
Branch on `error.code`, show `error.message`.
""".strip()


def operation_id(route: APIRoute) -> str:
    """Use the route function name as operationId (e.g. ``create_user``) so generated
    frontend clients get readable method names. Route function names must be unique."""
    return route.name


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the application."""
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        # Fixed title, not settings.app_name, so docs/openapi.json does not depend on .env.
        title="ExpenseFlow API",
        version="0.1.0",
        summary="Expense claims, policy checks, approvals, audit and payout.",
        description=API_DESCRIPTION,
        servers=[{"url": "http://localhost:8000", "description": "Local (docker compose)"}],
        generate_unique_id_function=operation_id,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    # Dev-only wide-open CORS so the Vite dev server can call the API.
    # Tighten the origins before anything leaves the laptop.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_observability(app)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()
