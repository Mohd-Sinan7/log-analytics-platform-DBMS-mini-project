"""
anomalies.py — /anomalies endpoints including live simulation and time-series feeds.
"""
from __future__ import annotations

import datetime
import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from anomaly.detector import _detect_once
from api.models import AnomalyEntry, AnomaliesResponse
from api.queries import query_anomalies

router = APIRouter(tags=["anomalies"])
logger = logging.getLogger("api.anomalies")


class SimulateRequest(BaseModel):
    service: str = "payments"
    spike_count: int = 1500


@router.get("/anomalies", response_model=AnomaliesResponse)
async def list_anomalies(
    request: Request,
    from_ts: Optional[datetime.datetime] = Query(None, alias="from"),
    to_ts:   Optional[datetime.datetime] = Query(None, alias="to"),
) -> AnomaliesResponse:
    """Return detected anomaly records."""
    rows = await query_anomalies(request.app.state.pg, from_ts, to_ts)
    return AnomaliesResponse(data=[AnomalyEntry(**dict(r)) for r in rows])


@router.get("/anomalies/timeseries")
async def get_timeseries_data(request: Request):
    """Return recent minute buckets with error volumes and anomaly flags for live frontend charts."""
    pg: asyncpg.Pool = request.app.state.pg
    
    rows = await pg.fetch(
        """
        WITH recent_buckets AS (
            SELECT 
                bucket,
                SUM(count) AS total_logs,
                SUM(CASE WHEN severity IN ('ERROR', 'FATAL') THEN count ELSE 0 END) AS error_logs
            FROM log_counts_minute
            WHERE bucket >= NOW() - INTERVAL '3 hours'
            GROUP BY bucket
            ORDER BY bucket ASC
        )
        SELECT 
            b.bucket,
            b.total_logs,
            b.error_logs,
            CASE WHEN a.id IS NOT NULL THEN true ELSE false END AS is_anomaly,
            COALESCE(a.zscore, 0) AS zscore,
            COALESCE(a.service, '') AS anomaly_service
        FROM recent_buckets b
        LEFT JOIN anomalies a ON b.bucket = a.bucket
        ORDER BY b.bucket ASC;
        """
    )
    
    points = []
    for r in rows:
        points.append({
            "bucket": r["bucket"].isoformat(),
            "time": r["bucket"].strftime("%H:%M"),
            "total_logs": int(r["total_logs"]),
            "error_logs": int(r["error_logs"]),
            "is_anomaly": bool(r["is_anomaly"]),
            "zscore": round(float(r["zscore"]), 2),
            "service": r["anomaly_service"],
        })
    return points


@router.post("/anomalies/simulate")
async def simulate_live_anomaly(req: SimulateRequest, request: Request):
    """
    Simulate a live traffic spike and immediately execute the Z-score anomaly detector.
    Demonstrates end-to-end real-time statistical anomaly detection, database triggers, and UI alert updates.
    """
    pg: asyncpg.Pool = request.app.state.pg
    service = req.service.lower()
    spike_count = max(50, req.spike_count)

    async with pg.acquire() as conn:
        now_m = await conn.fetchval("SELECT date_trunc('minute', NOW())")
        
        # 1. Ensure baseline of 1-4 errors per minute exists for previous 20 minutes
        for i in range(2, 22):
            b = now_m - datetime.timedelta(minutes=i)
            err_cnt = 2 if i % 2 == 0 else 3
            await conn.execute(
                """
                INSERT INTO log_counts_minute (bucket, service, severity, count)
                VALUES ($1, $2, 'ERROR', $3), ($1, $2, 'INFO', 50)
                ON CONFLICT (bucket, service, severity) 
                DO UPDATE SET count = EXCLUDED.count
                """,
                b, service, err_cnt,
            )

        # 2. Insert live spike into log_counts_minute
        await conn.execute(
            """
            INSERT INTO log_counts_minute (bucket, service, severity, count)
            VALUES ($1, $2, 'ERROR', $3), ($1, $2, 'INFO', 20)
            ON CONFLICT (bucket, service, severity) 
            DO UPDATE SET count = EXCLUDED.count
            """,
            now_m, service, spike_count,
        )

        # 3. Insert real sample error logs into the partitioned logs table
        sample_messages = [
            f"CRITICAL: Payment gateway circuit breaker tripped for {service} — HTTP 504 Gateway Timeout",
            f"ERROR: Connection pool exhausted while communicating with {service} downstream cluster",
            f"ERROR: Latency exceeded 5000ms SLA in {service}; transaction aborted",
            f"FATAL: Database replication lag exceeded safety threshold during {service} high-load burst",
            f"ERROR: Downstream payment provider returned error code 503 SERVICE_UNAVAILABLE",
        ]
        for msg in sample_messages:
            await conn.execute(
                """
                INSERT INTO logs (ts, severity, service, host, trace_id, message)
                VALUES (NOW(), 'ERROR', $1, 'host-01', 'tr-live-spike', $2)
                """,
                service, msg,
            )

    # 4. Trigger anomaly detection for this bucket
    await _detect_once(pg, zscore_threshold=3.0, min_count=5, bucket=now_m)

    # 5. Fetch detected anomaly
    latest_anomaly = await pg.fetchrow(
        "SELECT * FROM anomalies WHERE service = $1 ORDER BY id DESC LIMIT 1",
        service,
    )

    if latest_anomaly:
        res = dict(latest_anomaly)
        for k, v in res.items():
            if hasattr(v, "isoformat"):
                res[k] = v.isoformat()
        return {
            "status": "ANOMALY_DETECTED",
            "message": f"Successfully injected live error spike ({spike_count} errors) into '{service}'. Z-score exceeded threshold ({res['zscore']:.2f} > 3.0)!",
            "anomaly": res,
        }
    else:
        return {
            "status": "PROCESSED",
            "message": f"Injected {spike_count} errors, but baseline variance was high.",
        }
