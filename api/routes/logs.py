"""logs.py — /logs and /trace endpoints."""
from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from api.models import LogEntry, LogsResponse
from api.queries import query_logs, query_trace

router = APIRouter()


def _encode_cursor(ts: datetime, row_id: int) -> str:
    payload = json.dumps({"ts": ts.isoformat(), "id": row_id})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(payload["ts"]), int(payload["id"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid cursor: {exc}") from exc


@router.get("/logs", response_model=LogsResponse, tags=["logs"])
async def list_logs(
    request: Request,
    service:  Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    host:     Optional[str] = Query(None),
    from_ts:  Optional[datetime] = Query(None, alias="from"),
    to_ts:    Optional[datetime] = Query(None, alias="to"),
    limit:    int = Query(50, ge=1, le=1000),
    cursor:   Optional[str] = Query(None),
) -> LogsResponse:
    """Paginated log listing with keyset cursor."""
    cursor_ts: Optional[datetime] = None
    cursor_id: Optional[int]      = None
    if cursor:
        cursor_ts, cursor_id = _decode_cursor(cursor)

    rows = await query_logs(
        pool=request.app.state.pg,
        service=service,
        severity=severity,
        host=host,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        cursor_ts=cursor_ts,
        cursor_id=cursor_id,
    )

    entries = [LogEntry(**dict(r)) for r in rows]
    next_cursor = None
    if len(entries) == limit:
        last = entries[-1]
        next_cursor = _encode_cursor(last.ts, last.id)

    return LogsResponse(
        data=entries,
        next_cursor=next_cursor,
        total_returned=len(entries),
    )


@router.get("/trace/{trace_id}", response_model=LogsResponse, tags=["logs"])
async def get_trace(
    request: Request,
    trace_id: str,
) -> LogsResponse:
    """Return all log rows for a given trace_id, ordered by ts ASC."""
    rows = await query_trace(request.app.state.pg, trace_id)
    entries = [LogEntry(**dict(r)) for r in rows]
    return LogsResponse(data=entries, next_cursor=None, total_returned=len(entries))
