"""search.py — /search endpoint (Elasticsearch → Postgres hydration)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, Request
from api.es_client import es_search
from api.models import SearchHit, SearchResponse
from api.queries import hydrate_by_doc_ids

router = APIRouter()


@router.get("/search", response_model=SearchResponse, tags=["search"])
async def search_logs(
    request: Request,
    q:        str = Query(..., description="Search query"),
    fuzzy:    bool = Query(False),
    service:  Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    from_ts:  Optional[datetime] = Query(None, alias="from"),
    to_ts:    Optional[datetime] = Query(None, alias="to"),
    limit:    int = Query(50, ge=1, le=500),
) -> SearchResponse:
    """Full-text search via Elasticsearch; returns rows hydrated from Postgres."""
    hits, total = await es_search(
        es=request.app.state.es,
        q=q,
        fuzzy=fuzzy,
        service=service,
        severity=severity,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
    )

    doc_ids = [h["_id"] for h in hits]
    score_map = {h["_id"]: h["_score"] for h in hits}

    rows = await hydrate_by_doc_ids(request.app.state.pg, doc_ids)
    results = [
        SearchHit(**dict(r), score=score_map.get(str(r["doc_id"])))
        for r in rows
    ]
    return SearchResponse(data=results, total_hits=total)
