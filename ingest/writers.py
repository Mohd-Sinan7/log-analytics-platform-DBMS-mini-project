"""
writers.py — Batch writer: flushes rows to Postgres (COPY) and Elasticsearch (bulk).

Flushing strategy
-----------------
* Flush when the batch reaches *batch_size* rows (default 1000).
* Flush when *flush_interval* seconds have elapsed since the last flush.
* Failed rows are written to the Postgres dead_letter table.
* Retries use exponential back-off (max 3 attempts).
"""
from __future__ import annotations

import asyncio
import io
import logging
import time
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg
    from elasticsearch import AsyncElasticsearch

from ingest.parser import LogRecord, ParseError

logger = logging.getLogger("ingest.writers")

_RETRY_BASE = 0.5  # seconds
_MAX_RETRIES = 3
_ES_INDEX = "logs"


# ---------------------------------------------------------------------------
# Postgres helpers
# ---------------------------------------------------------------------------

async def _copy_to_postgres(
    conn: "asyncpg.Connection",
    records: list[LogRecord],
    doc_ids: list[str],
) -> None:
    """Bulk-insert *records* via asyncpg copy_records_to_table.

    Each record gets a pre-generated UUID (*doc_id*) that is also sent to ES
    so both stores share the same document identifier.
    """
    rows = [
        (uuid.UUID(doc_id), rec.ts, rec.severity, rec.service, rec.host, rec.trace_id, rec.message)
        for rec, doc_id in zip(records, doc_ids)
    ]
    await conn.copy_records_to_table(
        "logs",
        records=rows,
        columns=["doc_id", "ts", "severity", "service", "host", "trace_id", "message"],
    )


async def _write_dead_letter(
    conn: "asyncpg.Connection",
    raw_line: str,
    error: str,
) -> None:
    """Insert a failed row into dead_letter."""
    await conn.execute(
        "INSERT INTO dead_letter (raw_line, error) VALUES ($1, $2)",
        raw_line, error,
    )


# ---------------------------------------------------------------------------
# Elasticsearch helpers
# ---------------------------------------------------------------------------

async def _bulk_to_es(
    es: "AsyncElasticsearch",
    records: list[LogRecord],
    doc_ids: list[str],
) -> None:
    """Bulk-index *records* into Elasticsearch using provided *doc_ids*."""
    actions = []
    for rec, doc_id in zip(records, doc_ids):
        actions.append({"index": {"_index": _ES_INDEX, "_id": doc_id}})
        actions.append({
            "ts":       rec.ts.isoformat(),
            "severity": rec.severity,
            "service":  rec.service,
            "host":     rec.host,
            "trace_id": rec.trace_id,
            "message":  rec.message,
        })
    resp = await es.bulk(operations=actions, refresh=False)
    if resp.get("errors"):
        errors = [item for item in resp["items"] if item.get("index", {}).get("error")]
        logger.warning("ES bulk had %d errors (first: %s)", len(errors), errors[0] if errors else "?")


# ---------------------------------------------------------------------------
# Batch writer
# ---------------------------------------------------------------------------

class BatchWriter:
    """Accumulates :class:`LogRecord` objects and flushes them in batches."""

    def __init__(
        self,
        pg_pool: "asyncpg.Pool",
        es_client: "AsyncElasticsearch",
        batch_size: int = 1000,
        flush_interval: float = 1.0,
    ) -> None:
        self._pg   = pg_pool
        self._es   = es_client
        self._size = batch_size
        self._interval = flush_interval
        self._buf: list[LogRecord] = []
        self._doc_ids: list[str]  = []
        self._last_flush = time.monotonic()
        self._total_written = 0
        self._last_log_time = time.monotonic()
        self._since_last_log = 0

    async def add(self, record: LogRecord) -> None:
        """Add *record* to the buffer; flush automatically when thresholds hit."""
        doc_id = str(uuid.uuid4())
        self._buf.append(record)
        self._doc_ids.append(doc_id)

        if len(self._buf) >= self._size:
            await self.flush()
        elif (time.monotonic() - self._last_flush) >= self._interval:
            await self.flush()

    async def flush(self) -> None:
        """Flush the current buffer to Postgres and Elasticsearch."""
        if not self._buf:
            return

        records  = self._buf[:]
        doc_ids  = self._doc_ids[:]
        self._buf.clear()
        self._doc_ids.clear()
        self._last_flush = time.monotonic()

        await self._flush_with_retry(records, doc_ids)

        count = len(records)
        self._total_written += count
        self._since_last_log += count

        now = time.monotonic()
        if now - self._last_log_time >= 10.0:
            rate = self._since_last_log / (now - self._last_log_time)
            logger.info(
                "Ingest stats: %.1f lines/sec | total=%d",
                rate, self._total_written,
            )
            self._last_log_time = now
            self._since_last_log = 0

    async def _flush_with_retry(
        self,
        records: list[LogRecord],
        doc_ids: list[str],
    ) -> None:
        """Try to write *records* with exponential back-off; send failures to dead_letter."""
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with self._pg.acquire() as conn:
                    await _copy_to_postgres(conn, records, doc_ids)
                await _bulk_to_es(self._es, records, doc_ids)
                return
            except Exception as exc:
                logger.warning("Flush attempt %d/%d failed: %s", attempt, _MAX_RETRIES, exc)
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_BASE * (2 ** (attempt - 1)))

        # All retries exhausted — write to dead_letter
        logger.error("All %d retries failed; sending %d rows to dead_letter", _MAX_RETRIES, len(records))
        async with self._pg.acquire() as conn:
            for rec in records:
                await _write_dead_letter(conn, rec.raw, "Flush failed after max retries")

    async def close(self) -> None:
        """Flush any remaining buffered rows and release resources."""
        await self.flush()
