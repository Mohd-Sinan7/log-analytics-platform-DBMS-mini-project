"""
advanced.py — Routes executing advanced SQL queries required by the PES DBMS rubric:
- Multi-table JOIN queries
- Nested subqueries
- Correlated subqueries
- Recursive CTE queries (WITH RECURSIVE)
- Analytical window function CTEs
- Stored procedure execution
"""
from __future__ import annotations

import logging
from typing import Any, Optional
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from api.routes.auth import get_current_user, require_role

router = APIRouter(prefix="/api/v1/queries", tags=["advanced-queries"])
logger = logging.getLogger("api.advanced_queries")


def _get_pg(request: Request) -> asyncpg.Pool:
    return request.app.state.pg


class PartitionRequest(BaseModel):
    target_date: str  # YYYY-MM-DD


QUERIES = {
    "join": {
        "title": "Multi-Table Operational Telemetry Join",
        "description": "Joins partitioned logs, services dimension, hosts dimension, and anomalies table.",
        "sql": """
SELECT 
    l.id AS log_id,
    l.ts,
    l.severity,
    l.service,
    s.tier AS service_tier,
    s.owner_team,
    l.host,
    h.datacenter,
    l.message,
    a.zscore AS anomaly_zscore
FROM logs l
INNER JOIN services_dim s ON l.service = s.service_name
INNER JOIN hosts_dim h ON l.host = h.hostname
LEFT JOIN anomalies a 
    ON l.service = a.service 
    AND date_trunc('minute', l.ts) = a.bucket
ORDER BY l.ts DESC
LIMIT 50;
        """,
    },
    "nested": {
        "title": "Nested Subquery: Logs for Anomaly Services",
        "description": "Finds ERROR & FATAL logs occurring in services that recorded a zscore >= 3.0 anomaly.",
        "sql": """
SELECT l.id, l.ts, l.service, l.severity, l.host, l.message
FROM logs l
WHERE l.severity IN ('ERROR', 'FATAL')
  AND l.service IN (
      SELECT a.service 
      FROM anomalies a 
      WHERE a.zscore >= 3.0
  )
ORDER BY l.ts DESC
LIMIT 50;
        """,
    },
    "correlated": {
        "title": "Correlated Subquery: Services Exceeding Tier Average Error Count",
        "description": "Evaluates each service against the average error count of all services within the SAME architecture tier.",
        "sql": """
SELECT 
    s.service_name,
    s.tier,
    COUNT(l.id) AS service_error_count
FROM services_dim s
LEFT JOIN logs l ON s.service_name = l.service AND l.severity IN ('ERROR', 'FATAL')
GROUP BY s.service_name, s.tier
HAVING COUNT(l.id) > (
    SELECT COALESCE(AVG(tier_sub.err_cnt), 0)
    FROM (
        SELECT s_in.service_name, COUNT(l_in.id) AS err_cnt
        FROM services_dim s_in
        LEFT JOIN logs l_in ON s_in.service_name = l_in.service AND l_in.severity IN ('ERROR', 'FATAL')
        WHERE s_in.tier = s.tier
        GROUP BY s_in.service_name
    ) tier_sub
)
ORDER BY service_error_count DESC;
        """,
    },
    "recursive": {
        "title": "Recursive CTE: Zero-Gap Monitoring Time Generator",
        "description": "Generates a continuous sequence of 10-minute monitoring intervals recursively to detect telemetry gaps.",
        "sql": """
WITH RECURSIVE time_intervals AS (
    SELECT date_trunc('hour', NOW()) - INTERVAL '2 hours' AS interval_start
    UNION ALL
    SELECT interval_start + INTERVAL '10 minutes'
    FROM time_intervals
    WHERE interval_start < date_trunc('hour', NOW())
)
SELECT 
    ti.interval_start,
    COUNT(l.id) AS log_count,
    COUNT(CASE WHEN l.severity IN ('ERROR', 'FATAL') THEN 1 END) AS error_count
FROM time_intervals ti
LEFT JOIN logs l 
    ON l.ts >= ti.interval_start 
   AND l.ts < ti.interval_start + INTERVAL '10 minutes'
GROUP BY ti.interval_start
ORDER BY ti.interval_start;
        """,
    },
    "cte_window": {
        "title": "Analytical Window CTE: Error Velocity & Lag Analysis",
        "description": "Uses LAG(), MOVING AVERAGE, and RANK() window functions to calculate log velocity changes between minutes.",
        "sql": """
WITH minute_stats AS (
    SELECT 
        bucket,
        service,
        SUM(count) AS total_logs,
        SUM(CASE WHEN severity IN ('ERROR', 'FATAL') THEN count ELSE 0 END) AS error_logs
    FROM log_counts_minute
    WHERE bucket >= NOW() - INTERVAL '4 hours'
    GROUP BY bucket, service
),
velocity_analysis AS (
    SELECT 
        bucket,
        service,
        error_logs,
        LAG(error_logs, 1, 0) OVER (PARTITION BY service ORDER BY bucket) AS prev_minute_errors,
        AVG(error_logs) OVER (PARTITION BY service ORDER BY bucket ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS rolling_5m_avg_errors,
        RANK() OVER (PARTITION BY bucket ORDER BY error_logs DESC) AS error_rank_in_bucket
    FROM minute_stats
)
SELECT 
    bucket,
    service,
    error_logs,
    prev_minute_errors,
    (error_logs - prev_minute_errors) AS error_delta,
    ROUND(rolling_5m_avg_errors, 2) AS rolling_5m_avg,
    error_rank_in_bucket
FROM velocity_analysis
ORDER BY bucket DESC, error_logs DESC
LIMIT 50;
        """,
    },
}


@router.get("/list")
async def list_available_queries():
    """List available advanced queries for demonstrations."""
    return [
        {"id": k, "title": v["title"], "description": v["description"]}
        for k, v in QUERIES.items()
    ]


@router.get("/run/{query_id}")
async def run_query(query_id: str, pg: asyncpg.Pool = Depends(_get_pg)):
    """Execute one of the predefined advanced SQL queries and return results and execution metadata."""
    if query_id not in QUERIES:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found.")
    
    q_info = QUERIES[query_id]
    raw_sql = q_info["sql"].strip()
    
    try:
        # Run explain analyze for query execution plan
        explain_rows = await pg.fetch(f"EXPLAIN ANALYZE {raw_sql}")
        plan = [r["QUERY PLAN"] for r in explain_rows]
        
        # Execute query
        rows = await pg.fetch(raw_sql)
        results = [dict(r) for r in rows]
        
        # Format timestamps / non-JSON types
        for row in results:
            for k, val in row.items():
                if hasattr(val, "isoformat"):
                    row[k] = val.isoformat()
                elif hasattr(val, "__float__"):
                    row[k] = float(val)
        
        return {
            "query_id": query_id,
            "title": q_info["title"],
            "description": q_info["description"],
            "sql": raw_sql,
            "row_count": len(results),
            "execution_plan": plan,
            "data": results,
        }
    except Exception as exc:
        logger.exception("Failed to run query %s: %s", query_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/procedure/partition")
async def call_partition_procedure(
    req: PartitionRequest,
    current_user: dict = Depends(require_role(["admin"])),
    pg: asyncpg.Pool = Depends(_get_pg),
):
    """Execute stored procedure pr_create_daily_partition (Admin only)."""
    try:
        await pg.execute("CALL pr_create_daily_partition($1::date)", req.target_date)
        
        # Audit log entry
        await pg.execute(
            """
            INSERT INTO audit_log (username, action, entity, details)
            VALUES ($1, 'PROCEDURE_EXECUTE', 'partitions', $2::jsonb)
            """,
            current_user["username"],
            f'{{"procedure": "pr_create_daily_partition", "target_date": "{req.target_date}"}}',
        )
        return {"status": "success", "message": f"Procedure pr_create_daily_partition({req.target_date}) executed."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/audit")
async def get_audit_logs(
    current_user: dict = Depends(require_role(["admin"])),
    pg: asyncpg.Pool = Depends(_get_pg),
):
    """Retrieve database audit log records (Admin only)."""
    rows = await pg.fetch("SELECT * FROM audit_log ORDER BY id DESC LIMIT 50")
    results = [dict(r) for r in rows]
    for row in results:
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
    return results
