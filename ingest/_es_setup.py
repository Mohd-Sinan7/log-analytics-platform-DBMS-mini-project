"""
_es_setup.py — Elasticsearch index creation with explicit mapping.
"""
from __future__ import annotations

import logging
from elasticsearch import AsyncElasticsearch, NotFoundError

logger = logging.getLogger("ingest.es_setup")

INDEX_NAME = "logs"

MAPPING = {
    "settings": {
        "number_of_shards":   1,
        "number_of_replicas": 0,
        "refresh_interval":   "5s",
    },
    "mappings": {
        "properties": {
            "ts":       {"type": "date"},
            "severity": {"type": "keyword"},
            "service":  {"type": "keyword"},
            "host":     {"type": "keyword"},
            "trace_id": {"type": "keyword"},
            "message":  {"type": "text", "analyzer": "standard"},
        }
    },
}


async def ensure_index(es: AsyncElasticsearch) -> None:
    """Create the logs index if it does not already exist."""
    try:
        exists = await es.indices.exists(index=INDEX_NAME)
        if not exists:
            await es.indices.create(index=INDEX_NAME, mappings=MAPPING["mappings"], settings=MAPPING["settings"])
            logger.info("Created Elasticsearch index '%s'", INDEX_NAME)
        else:
            logger.info("Elasticsearch index '%s' already exists", INDEX_NAME)
    except Exception as exc:
        logger.error("Failed to ensure ES index: %s", exc)
        raise
