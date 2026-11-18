"""
main.py — FastAPI application entry point.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import asyncpg
from elasticsearch import AsyncElasticsearch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health, logs, search, stats, anomalies, auth, advanced, nosql

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("api.main")


def _pg_dsn() -> str:
    host     = os.environ.get("POSTGRES_HOST", "localhost")
    port     = os.environ.get("POSTGRES_PORT", "5432")
    db       = os.environ.get("POSTGRES_DB", "logs")
    user     = os.environ.get("POSTGRES_USER", "logs")
    password = os.environ.get("POSTGRES_PASSWORD", "logspassword")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Postgres pool and ES client lifecycle."""
    pool = await asyncpg.create_pool(_pg_dsn(), min_size=2, max_size=20)
    es   = AsyncElasticsearch(os.environ.get("ES_HOST", "http://localhost:9200"))

    # Ensure ES index mapping exists
    from ingest._es_setup import ensure_index
    try:
        await ensure_index(es)
    except Exception as exc:
        logger.warning("Could not ensure ES index at startup: %s", exc)

    app.state.pg = pool
    app.state.es = es
    logger.info("Startup complete")
    yield
    await es.close()
    await pool.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Log Analytics Platform",
    description="A self-hosted SQL-first log analytics API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)

# Mount core routers under /api/v1 (for frontend client)
app.include_router(logs.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(anomalies.router, prefix="/api/v1")

# Also mount under root (for legacy curl / health checks)
app.include_router(logs.router)
app.include_router(search.router)
app.include_router(stats.router)
app.include_router(anomalies.router)

app.include_router(auth.router)
app.include_router(advanced.router)
app.include_router(nosql.router)
