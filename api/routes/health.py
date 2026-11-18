"""health.py — /health endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Request
from api.models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health(request: Request) -> HealthResponse:
    """Liveness + dependency health check."""
    pg_status = "ok"
    es_status = "ok"

    try:
        async with request.app.state.pg.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception as exc:
        pg_status = f"error: {exc}"

    try:
        info = await request.app.state.es.cluster.health()
        es_status = info.get("status", "unknown")
    except Exception as exc:
        es_status = f"error: {exc}"

    overall = "ok" if pg_status == "ok" and es_status in ("green", "yellow", "ok") else "degraded"
    return HealthResponse(status=overall, postgres=pg_status, elasticsearch=es_status)
