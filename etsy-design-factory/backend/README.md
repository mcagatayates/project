# Design Factory backend

FastAPI + SQLAlchemy + Celery backend for the autonomous Etsy wall-art
Design Factory. See `../docs/` for the full architecture; this file is
just "how do I run it."

## Local setup (no Docker)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env   # then edit if you want real providers
```

By default `APP_ENV=development` and `PROVIDER_MODE=fake`, so nothing
here talks to a paid API. `DATABASE_URL` defaults to a local SQLite file,
which is fine for exploring the system but is **not** what
`docs/DATABASE.md` designates as the source of truth in production —
point it at Postgres for anything beyond local exploration:

```bash
export DATABASE_URL=postgresql+psycopg2://design_factory:pass@localhost:5432/design_factory
alembic upgrade head
```

## Running the API

```bash
uvicorn app.main:app --reload
# http://localhost:8000/health
```

## Running a worker (needs Redis, or set CELERY_TASK_ALWAYS_EAGER=true)

```bash
celery -A app.queue.celery_app worker -Q analysis,concepts,generation,vision_qc,repair,image_processing,mockups,exports --loglevel=INFO
```

## Tests

```bash
pytest            # full suite, ~60-70s (the acceptance test simulates a full production day)
pytest -k "not acceptance"   # skip the slow end-to-end simulation for a fast inner loop
ruff check app tests
ruff format app tests
mypy app
```

Tests run against an in-memory SQLite database with every provider role
forced to its deterministic fake adapter (`PROVIDER_MODE=fake` /
`APP_ENV=test`, set in `tests/conftest.py`) and Celery in eager mode — no
Postgres, Redis, or paid API required.

## Migrations

```bash
alembic upgrade head              # apply
alembic revision --autogenerate -m "message"   # after changing app/db/models/*
alembic downgrade -1              # roll back one
```

Autogenerate needs a real (even empty) database to diff against; a
throwaway SQLite file works fine for generating the migration script even
though it will actually be applied to Postgres:

```bash
DATABASE_URL=sqlite+pysqlite:///./_gen.db alembic revision --autogenerate -m "..."
rm _gen.db
```

## Smoke-testing the full pipeline without pytest

```python
import asyncio, datetime
from app.db.models import Base
from app.db.session import get_engine, get_sessionmaker
from app.providers.factory import build_registry
from app.simulation.daily_simulation import run_daily_simulation

Base.metadata.create_all(get_engine())
session = get_sessionmaker()()
registry = build_registry()
result = asyncio.run(run_daily_simulation(session, registry, plan_date=datetime.date.today(), target_final_designs=30))
session.commit()
print(len(result.approved_artworks), "approved")
```
