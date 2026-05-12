from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine = None
_SessionLocal = None


def configure_db() -> None:
    global _engine, _SessionLocal
    settings = get_settings()
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(settings.database_url, pool_pre_ping=True)
    _SessionLocal = sessionmaker(
        bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


def get_engine():
    global _engine
    if _engine is None:
        configure_db()
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        configure_db()
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def reset_db_engine() -> None:
    """Dispose engine and clear factories. For tests after changing DATABASE_URL."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
        _engine = None
    _SessionLocal = None
