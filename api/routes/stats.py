"""stats.py — /stats/* endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, Request
from api.models import ErrorRateBucket, ErrorRateResponse, TopHost, TopHostsResponse
from api.queries import query_error_rate, query_top_hosts

router = APIRouter(prefix="/stats")


@router.get("/error-rate", response_model=ErrorRateResponse, tags=["stats"])
async def error_rate(
    request: Request,
    service:  Optional[str] = Query(None),
    from_ts:  Optional[datetime] = Query(None, alias="from"),
    to_ts:    Optional[datetime] = Query(None, alias="to"),
    interval: str = Query("1m", pattern="^(1m|5m|1h)$"),
) -> ErrorRateResponse:
    """Bucketed error rate from the rollup table."""
    rows = await query_error_rate(
        pool=request.app.state.pg,
        service=service,
        from_ts=from_ts,
        to_ts=to_ts,
        interval=interval,
    )
    buckets = []
    for r in rows:
        total = r["total_count"] or 0
        errors = r["error_count"] or 0
        buckets.append(ErrorRateBucket(
            bucket=r["bucket"],
            service=r["service"],
            error_count=int(errors),
            total_count=int(total),
            error_rate=round(errors / total, 4) if total > 0 else 0.0,
        ))
    return ErrorRateResponse(data=buckets, interval=interval)


@router.get("/top-hosts", response_model=TopHostsResponse, tags=["stats"])
async def top_hosts(
    request: Request,
    severity: str = Query("ERROR"),
    from_ts:  Optional[datetime] = Query(None, alias="from"),
    to_ts:    Optional[datetime] = Query(None, alias="to"),
) -> TopHostsResponse:
    """Top 10 noisiest hosts for a given severity."""
    rows = await query_top_hosts(
        pool=request.app.state.pg,
        severity=severity,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    return TopHostsResponse(
        data=[TopHost(host=r["host"], count=r["count"]) for r in rows],
        severity=severity,
    )
