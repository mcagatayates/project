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
def registry(db_session, storage_root):
    from app.providers.factory import build_registry
    from app.providers.health import make_db_health_hook

    return build_registry(on_health_event=make_db_health_hook(db_session))


@pytest.fixture()
def collection(db_session):
    from app.db.models.collection import Collection
    from app.db.models.enums import CollectionStatus, ProductionMode

    c = Collection(
        name="Calm Botanicals",
        thesis="Quiet, minimal botanical studies for renters who want warmth without clutter.",
        target_aesthetic="japandi botanical",
        target_customer_hypothesis="modern-boho renters, 25-40, small apartments",
        palette_boundaries={"allowed_palette_names": ["sage-clay", "ochre-ink", "seafoam-neutral", "dusk-plum"]},
        medium="gouache",
        subject_families=["botanical"],
        composition_diversity_requirements={"min_layout_types": 2},
        target_design_count=10,
        experimental_variables={},
        status=CollectionStatus.DISCOVERY.value,
        mode=ProductionMode.DISCOVERY.value,
    )
    db_session.add(c)
    db_session.flush()
    return c


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
