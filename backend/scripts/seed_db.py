"""Load ``db/seed.sql`` (idempotent, synthetic data) into the configured database.

    python -m scripts.seed_db

Runs the file as-is through psycopg, so the container needs no ``psql``. The file
manages its own transaction (``BEGIN`` ... ``COMMIT``) and uses ``ON CONFLICT DO
NOTHING``, so running it on every start is safe.
"""

from __future__ import annotations

import logging
from pathlib import Path

import psycopg

from app.config import get_settings

logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).resolve().parent.parent / "db" / "seed.sql"


def psycopg_url(database_url: str) -> str:
    """``postgresql+psycopg://...`` (SQLAlchemy) -> ``postgresql://...`` (libpq)."""
    scheme, _, rest = database_url.partition("://")
    return f"{scheme.split('+', 1)[0]}://{rest}"


def run(seed_file: Path = SEED_FILE) -> None:
    sql = seed_file.read_text(encoding="utf-8")
    with psycopg.connect(psycopg_url(get_settings().database_url), autocommit=True) as conn:
        conn.execute(sql)
    logger.info("Seed data loaded from %s", seed_file.name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s | %(message)s")
    run()
