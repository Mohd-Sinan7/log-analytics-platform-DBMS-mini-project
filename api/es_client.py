"""
es_client.py — Elasticsearch query helpers.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from elasticsearch import AsyncElasticsearch


async def es_search(
    es: AsyncElasticsearch,
    q: str,
    fuzzy: bool = False,
    service: Optional[str] = None,
    severity: Optional[str] = None,
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """Execute a full-text search and return (hits, total_hits).

    Each hit is a dict with ``_id`` and ``_score``.
    """
    must: list[dict] = []

    if fuzzy:
        must.append({
            "match": {
                "message": {
                    "query": q,
                    "fuzziness": "AUTO",
                }
            }
        })
    else:
        must.append({
            "match_phrase": {"message": q}
        })

    filters: list[dict] = []
    if service:
        filters.append({"term": {"service": service}})
    if severity:
        filters.append({"term": {"severity": severity}})

    range_filter: dict = {}
    if from_ts:
        range_filter["gte"] = from_ts.isoformat()
    if to_ts:
        range_filter["lte"] = to_ts.isoformat()
    if range_filter:
        filters.append({"range": {"ts": range_filter}})

    query: dict = {
        "bool": {
            "must": must,
            "filter": filters,
        }
    }

    resp = await es.search(
        index="logs",
        body={
            "query": query,
            "size": limit,
            "_source": False,
        },
    )

    total = resp["hits"]["total"]["value"]
    hits = [
        {"_id": h["_id"], "_score": h["_score"]}
        for h in resp["hits"]["hits"]
    ]
    return hits, total
