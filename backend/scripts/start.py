"""Container entrypoint: wait for the database, migrate, seed, then run the API.

    python -m scripts.start

Every step is idempotent, so a restart or a fresh volume both end in the same
state: ``alembic upgrade head`` applies only missing migrations, the seed uses
``ON CONFLICT DO NOTHING``, and the API inserts any missing default policy rules
when it starts. Set ``SEED_ON_START=false`` to skip the seed.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from alembic import command
from app.config import get_settings
from scripts import seed_db

logger = logging.getLogger("startup")

BACKEND_DIR = Path(__file__).resolve().parent.parent
DB_WAIT_SECONDS = 60


def wait_for_database(url: str, timeout: int = DB_WAIT_SECONDS) -> None:
    """Compose already waits for the db healthcheck; this covers a slow first start."""
    engine = create_engine(url, pool_pre_ping=True)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return
            except OperationalError:
                if time.monotonic() > deadline:
                    raise
                logger.info("Database not reachable yet; retrying")
                time.sleep(2)
    finally:
        engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s | %(message)s")
    settings = get_settings()

    wait_for_database(settings.database_url)

    logger.info("Applying database migrations")
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    # alembic.ini's logging config sets the root logger to WARN; restore INFO for the rest.
    logging.getLogger().setLevel(logging.INFO)

    if os.environ.get("SEED_ON_START", "true").lower() != "false":
        logger.info("Loading seed data")
        seed_db.run()

    port = os.environ.get("PORT", "8000")
    logger.info("Starting the API on port %s", port)
    os.execvp(
        "uvicorn",
        ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port, "--proxy-headers"],
    )


if __name__ == "__main__":
    main()
