"""Per-task DB session + ProviderRegistry setup. Each Celery task gets its
own session (workers are separate processes/threads; sessions are not
shared across task boundaries -- see docs/ARCHITECTURE.md "every handoff
is a row in Postgres")."""

from __future__ import annotations

from contextlib import contextmanager

from app.db.session import get_sessionmaker
from app.providers.factory import build_registry
from app.providers.health import make_db_health_hook


@contextmanager
def task_context():
    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        registry = build_registry(on_health_event=make_db_health_hook(session))
        yield session, registry
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
