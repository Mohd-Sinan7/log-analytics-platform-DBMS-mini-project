"""
queries.py — Parameterized SQL helpers for the Log Analytics API.

All queries use $N placeholders (asyncpg style). No string interpolation
of user-provided values.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import asyncpg


# ---------------------------------------------------------------------------
# Logs list with keyset pagination
# ---------------------------------------------------------------------------

async def query_logs(
    pool: asyncpg.Pool,
    service: Optional[str],
    severity: Optional[str],
    host: Optional[str],
    from_ts: Optional[datetime],
    to_ts: Optional[datetime],
    limit: int,
    cursor_ts: Optional[datetime],
    cursor_id: Optional[int],
) -> list[asyncpg.Record]:
    """Keyset-paginated log query.

    The cursor encodes (ts, id) from the last row of the previous page.
    """
    conditions = []
    params: list = []
    n = 1

    if service:
        conditions.append(f"service = ${n}")
        params.append(service)
        n += 1
    if severity:
        conditions.append(f"severity = ${n}")
        params.append(severity)
        n += 1
    if host:
        conditions.append(f"host = ${n}")
        params.append(host)
        n += 1
    if from_ts:
        conditions.append(f"ts >= ${n}")
        params.append(from_ts)
        n += 1
    if to_ts:
        conditions.append(f"ts <= ${n}")
        params.append(to_ts)
        n += 1
    if cursor_ts is not None and cursor_id is not None:
        conditions.append(f"(ts, id) < (${n}, ${n+1})")
        params.append(cursor_ts)
        params.append(cursor_id)
        n += 2

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"""
        SELECT id, doc_id, ts, severity, service, host, trace_id, message
        FROM logs
        {where}
        ORDER BY ts DESC, id DESC
        LIMIT ${n}
    """
    params.append(limit)

    async with pool.acquire() as conn:
        return await conn.fetch(sql, *params)


# ---------------------------------------------------------------------------
# Trace lookup
# ---------------------------------------------------------------------------

async def query_trace(
    pool: asyncpg.Pool,
    trace_id: str,
) -> list[asyncpg.Record]:
    sql = """
        SELECT id, doc_id, ts, severity, service, host, trace_id, message
        FROM logs
        WHERE trace_id = $1
        ORDER BY ts ASC
    """
    async with pool.acquire() as conn:
        return await conn.fetch(sql, trace_id)


# ---------------------------------------------------------------------------
# Hydrate rows by doc_id (for ES search results)
# ---------------------------------------------------------------------------

async def hydrate_by_doc_ids(
    pool: asyncpg.Pool,
    doc_ids: list[str],
) -> list[asyncpg.Record]:
    if not doc_ids:
        return []
    sql = """
        SELECT id, doc_id, ts, severity, service, host, trace_id, message
        FROM logs
        WHERE doc_id = ANY($1::uuid[])
        ORDER BY ts DESC
    """
    async with pool.acquire() as conn:
        return await conn.fetch(sql, doc_ids)


# ---------------------------------------------------------------------------
# Error rate aggregation
# ---------------------------------------------------------------------------

async def query_error_rate(
    pool: asyncpg.Pool,
    service: Optional[str],
    from_ts: Optional[datetime],
    to_ts: Optional[datetime],
    interval: str,
) -> list[asyncpg.Record]:
    """Return bucketed error counts from log_counts_minute or raw logs."""
    trunc = {
        "1m": "minute",
        "5m": "5 minutes",
        "1h": "hour",
    }.get(interval, "minute")

    conditions = ["1=1"]
    params: list = []
    n = 1

    if service:
        conditions.append(f"service = ${n}")
        params.append(service)
        n += 1
    if from_ts:
        conditions.append(f"bucket >= ${n}")
        params.append(from_ts)
        n += 1
    if to_ts:
        conditions.append(f"bucket <= ${n}")
        params.append(to_ts)
        n += 1

    where = " AND ".join(conditions)

    if interval == "1m":
        # Use pre-aggregated rollup table
        sql = f"""
            SELECT
                bucket,
                service,
                SUM(CASE WHEN severity IN ('ERROR','FATAL') THEN count ELSE 0 END) AS error_count,
                SUM(count) AS total_count
            FROM log_counts_minute
            WHERE {where}
            GROUP BY 1, 2
            ORDER BY 1 ASC
        """
    else:
        # Re-aggregate from rollup at coarser granularity
        sql = f"""
            SELECT
                date_trunc('{trunc}', bucket) AS bucket,
                service,
                SUM(CASE WHEN severity IN ('ERROR','FATAL') THEN count ELSE 0 END) AS error_count,
                SUM(count) AS total_count
            FROM log_counts_minute
            WHERE {where}
            GROUP BY 1, 2
            ORDER BY 1 ASC
        """

    async with pool.acquire() as conn:
        return await conn.fetch(sql, *params)


# ---------------------------------------------------------------------------
# Top hosts
# ---------------------------------------------------------------------------

async def query_top_hosts(
    pool: asyncpg.Pool,
    severity: str,
    from_ts: Optional[datetime],
    to_ts: Optional[datetime],
    limit: int = 10,
) -> list[asyncpg.Record]:
    conditions = ["severity = $1"]
    params: list = [severity]
    n = 2

    if from_ts:
        conditions.append(f"ts >= ${n}")
        params.append(from_ts)
        n += 1
    if to_ts:
        conditions.append(f"ts <= ${n}")
        params.append(to_ts)
        n += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT host, COUNT(*) AS count
        FROM logs
        WHERE {where}
        GROUP BY host
        ORDER BY count DESC
        LIMIT ${n}
    """
    params.append(limit)

    async with pool.acquire() as conn:
        return await conn.fetch(sql, *params)


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------

async def query_anomalies(
    pool: asyncpg.Pool,
    from_ts: Optional[datetime],
    to_ts: Optional[datetime],
) -> list[asyncpg.Record]:
    conditions = []
    params: list = []
    n = 1

    if from_ts:
        conditions.append(f"detected_at >= ${n}")
        params.append(from_ts)
        n += 1
    if to_ts:
        conditions.append(f"detected_at <= ${n}")
        params.append(to_ts)
        n += 1

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"""
        SELECT id, detected_at, bucket, service, metric, value,
               baseline_mean, baseline_std, zscore
        FROM anomalies
        {where}
        ORDER BY detected_at DESC
        LIMIT 500
    """
    async with pool.acquire() as conn:
        return await conn.fetch(sql, *params)
