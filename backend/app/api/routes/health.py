import time
from typing import Any

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.api.dependencies import AppSettings, DatabaseSession
from app.schemas.common import HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(status="ok", service="api", details={"local": True})


@router.get("/readiness", response_model=HealthStatus)
async def readiness(session: DatabaseSession, settings: AppSettings) -> HealthStatus:
    checks: dict[str, dict[str, Any]] = {}

    try:
        started = time.perf_counter()
        session.execute(text("SELECT 1"))
        checks["postgres"] = {
            "status": "ready",
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    except Exception:
        checks["postgres"] = {"status": "unavailable"}

    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in {
            "qdrant": f"{settings.qdrant_url.rstrip('/')}/readyz",
            "ollama": f"{settings.ollama_base_url.rstrip('/')}/api/tags",
        }.items():
            started = time.perf_counter()
            try:
                response = await client.get(url)
                response.raise_for_status()
                checks[name] = {
                    "status": "ready",
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                }
            except httpx.HTTPError:
                checks[name] = {"status": "unavailable"}

    overall = "ok" if all(item["status"] == "ready" for item in checks.values()) else "degraded"
    return HealthStatus(status=overall, service="api", details={"dependencies": checks})
