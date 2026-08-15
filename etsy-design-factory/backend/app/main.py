"""FastAPI app for the Production Dashboard / Human Control Center API.
Thin by design (see docs/ARCHITECTURE.md) -- reads/writes rows and
triggers plan generation; all paid-provider work happens in Celery
workers (app/queue/tasks), never inline here.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    approvals,
    artwork_assets,
    candidates,
    dashboard,
    drive_archive,
    getvela,
    market_intelligence,
    production,
)
from app.config import get_settings

app = FastAPI(title="Etsy Design Factory API", version="0.1.0")

settings = get_settings()
# Restrictive by default; widen via an env-driven allowlist in production
# rather than "*" (never expose this API to arbitrary origins).
_allowed_origins = [settings.frontend_origin]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Minimal in-process rate limiter (per-IP sliding window). This is a
# starting point, not a distributed limiter -- a multi-worker production
# deployment should replace this with a Redis-backed limiter shared across
# processes (see docs/PROVIDER_ARCHITECTURE.md rate_limit.py for the same
# caveat on the provider side).
_REQUEST_LOG: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_PER_MINUTE = 120


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _REQUEST_LOG[client_ip]
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= _RATE_LIMIT_PER_MINUTE:
        return JSONResponse(status_code=429, content={"detail": "rate limit exceeded"})
    window.append(now)
    return await call_next(request)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(dashboard.router)
app.include_router(candidates.router)
app.include_router(approvals.router)
app.include_router(production.router)
app.include_router(market_intelligence.router)
app.include_router(artwork_assets.router)
app.include_router(getvela.router)
app.include_router(drive_archive.router)
