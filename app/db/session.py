"""Database session and engine management using SQLAlchemy 2."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""

    pass


def get_engine():
    """Builds and returns the SQLAlchemy engine."""
    settings = get_settings()
    url = settings.DATABASE_URL
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        url,
        echo=False,
        future=True,
        connect_args=connect_args,
    )
    return engine


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Creates all defined database tables."""
    from app.db import models  # noqa: F401 - Ensure all models are registered

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
