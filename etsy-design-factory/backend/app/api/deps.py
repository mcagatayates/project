"""Shared FastAPI dependencies. The API is intentionally thin: it never
calls a provider or does image processing inline (see
docs/ARCHITECTURE.md "Request path vs. background path") -- it reads/
writes rows and enqueues Celery tasks."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import get_sessionmaker


def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
