"""
nosql.py — Elasticsearch NoSQL feature operations (RUD: Read, Update, Delete, Create).
Fulfills PES University DBMS Evaluation Criterion 9: NoSQL/Vector feature RUD (7 marks).
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/nosql", tags=["nosql-operations"])
logger = logging.getLogger("api.nosql")


def _get_es(request: Request) -> AsyncElasticsearch:
    return request.app.state.es


class CreateDocRequest(BaseModel):
    service: str
    severity: str
    host: str
    message: str
    trace_id: Optional[str] = None


class UpdateDocRequest(BaseModel):
    message: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None


@router.post("/documents", status_code=201)
async def create_document(doc: CreateDocRequest, es: AsyncElasticsearch = Depends(_get_es)):
    """Create / Index a new document into Elasticsearch index 'logs' (Create)."""
    body = {
        "service": doc.service,
        "severity": doc.severity,
        "host": doc.host,
        "message": doc.message,
        "trace_id": doc.trace_id,
        "created_at": "now",
    }
    resp = await es.index(index="logs", document=body, refresh=True)
    return {
        "status": "created",
        "_id": resp["_id"],
        "result": resp["result"],
        "index": resp["_index"],
    }


@router.get("/documents/{doc_id}")
async def read_document(doc_id: str, es: AsyncElasticsearch = Depends(_get_es)):
    """Read a document by _id from Elasticsearch (Read)."""
    try:
        resp = await es.get(index="logs", id=doc_id)
        return {
            "_id": resp["_id"],
            "found": resp["found"],
            "source": resp["_source"],
        }
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found: {exc}")


@router.put("/documents/{doc_id}")
async def update_document(
    doc_id: str,
    update: UpdateDocRequest,
    es: AsyncElasticsearch = Depends(_get_es),
):
    """Update fields in an existing Elasticsearch document (Update)."""
    doc_updates = {}
    if update.message is not None:
        doc_updates["message"] = update.message
    if update.tags is not None:
        doc_updates["tags"] = update.tags
    if update.status is not None:
        doc_updates["status"] = update.status
    
    if not doc_updates:
        raise HTTPException(status_code=400, detail="No fields provided for update.")
    
    try:
        resp = await es.update(index="logs", id=doc_id, doc=doc_updates, refresh=True)
        return {
            "status": "updated",
            "_id": resp["_id"],
            "result": resp["result"],
            "version": resp["_version"],
        }
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Document update failed: {exc}")


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, es: AsyncElasticsearch = Depends(_get_es)):
    """Delete a document by _id from Elasticsearch (Delete)."""
    try:
        resp = await es.delete(index="logs", id=doc_id, refresh=True)
        return {
            "status": "deleted",
            "_id": resp["_id"],
            "result": resp["result"],
        }
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Document deletion failed: {exc}")


@router.get("/aggregations")
async def get_elasticsearch_aggregations(es: AsyncElasticsearch = Depends(_get_es)):
    """Execute NoSQL bucket aggregations on service and severity."""
    try:
        query = {
            "size": 0,
            "aggs": {
                "services": {
                    "terms": {"field": "service", "size": 10}
                },
                "severities": {
                    "terms": {"field": "severity", "size": 10}
                }
            }
        }
        resp = await es.search(index="logs", body=query)
        return {
            "total_documents": resp["hits"]["total"]["value"],
            "aggregations": resp.get("aggregations", {})
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
