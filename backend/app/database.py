"""Database engine, session factory and the FastAPI session dependency."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Base class for ORM models.

    Domain models go in their own modules and inherit from this. Import them
    somewhere that runs at startup (or in Alembic's env.py) so that
    ``Base.metadata`` sees them before migrations are generated.
    """


# pool_pre_ping avoids handing out connections the database has already dropped,
# which happens routinely when the DB container restarts during a drill.
engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session]:
    """Yield a database session for the lifetime of one request.

    Commits are the caller's responsibility; the session is always closed, and
    rolled back if the request raised.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
