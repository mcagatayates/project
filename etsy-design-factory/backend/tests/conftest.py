import os

# Must run before any `app.*` module is imported anywhere in the test
# session, so it lives at module scope in the first-loaded conftest.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("PROVIDER_MODE", "fake")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("STORAGE_BACKEND", "local")

import shutil  # noqa: E402
import tempfile  # noqa: E402

import pytest  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.db.session import get_engine, get_sessionmaker  # noqa: E402

get_settings.cache_clear()


@pytest.fixture()
def db_session():
    engine = get_engine()
    Base.metadata.create_all(engine)
    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def storage_root():
    tmp = tempfile.mkdtemp(prefix="edf-storage-")
    old = os.environ.get("STORAGE_LOCAL_ROOT")
    os.environ["STORAGE_LOCAL_ROOT"] = tmp
    get_settings.cache_clear()
    yield tmp
    if old is not None:
        os.environ["STORAGE_LOCAL_ROOT"] = old
    else:
        os.environ.pop("STORAGE_LOCAL_ROOT", None)
    get_settings.cache_clear()
    shutil.rmtree(tmp, ignore_errors=True)
