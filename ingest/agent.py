"""
agent.py — Asyncio log-tailing / back-fill ingest agent.

Modes
-----
* **tail** (default): Watch a file with watchdog; track offset in a state file;
  handle log rotation (the file being recreated after rename/truncation).
* **backfill**: Read a file from start to end as fast as possible.

The agent calls create_partitions() on Postgres startup and every hour,
and refreshes the rollup table every 30 seconds.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

import asyncpg
from elasticsearch import AsyncElasticsearch
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ingest.config import get_config
from ingest.parser import ParseError, parse_line
from ingest.writers import BatchWriter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ingest.agent")

_PARTITION_INTERVAL = 3600   # seconds
_ROLLUP_INTERVAL    = 30     # seconds


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def _load_state(state_file: str) -> dict:
    try:
        with open(state_file) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state_file: str, state: dict) -> None:
    dirname = os.path.dirname(state_file)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(state, f)


# ---------------------------------------------------------------------------
# Partition & rollup maintenance
# ---------------------------------------------------------------------------

async def _maintain_partitions(pool: asyncpg.Pool) -> None:
    """Call create_partitions every hour."""
    while True:
        try:
            async with pool.acquire() as conn:
                await conn.execute("SELECT create_partitions(7)")
            logger.info("Partitions provisioned")
        except Exception as exc:
            logger.error("Partition maintenance failed: %s", exc)
        await asyncio.sleep(_PARTITION_INTERVAL)


async def _maintain_rollup(pool: asyncpg.Pool) -> None:
    """Refresh log_counts_minute every 30 seconds."""
    while True:
        await asyncio.sleep(_ROLLUP_INTERVAL)
        try:
            async with pool.acquire() as conn:
                await conn.execute("SELECT refresh_log_counts()")
        except Exception as exc:
            logger.error("Rollup refresh failed: %s", exc)


# ---------------------------------------------------------------------------
# Watchdog integration (asyncio bridge)
# ---------------------------------------------------------------------------

class _AsyncQueueHandler(FileSystemEventHandler):
    """Puts watchdog file events into an asyncio queue."""

    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._queue = queue
        self._loop  = loop

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, ("modified", event.src_path))

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, ("created", event.src_path))


# ---------------------------------------------------------------------------
# Core tailing logic
# ---------------------------------------------------------------------------

async def _tail_file(
    log_file: str,
    writer: BatchWriter,
    pool: asyncpg.Pool,
    state_file: str,
) -> None:
    """Tail *log_file*, parse lines, and feed parsed records to *writer*."""
    state   = _load_state(state_file)
    offset  = state.get(log_file, 0)
    loop    = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    handler  = _AsyncQueueHandler(queue, loop)
    observer = Observer()
    watch_dir = str(Path(log_file).parent)
    os.makedirs(watch_dir, exist_ok=True)
    observer.schedule(handler, watch_dir, recursive=False)
    observer.start()
    logger.info("Watching %s from offset %d", log_file, offset)

    async def _dead_letter(raw: str, err: str) -> None:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO dead_letter (raw_line, error) VALUES ($1, $2)",
                raw, err,
            )

    try:
        # Process any data already in the file before first event
        if os.path.exists(log_file):
            with open(log_file, "r", errors="replace") as fh:
                fh.seek(offset)
                for raw in fh:
                    try:
                        await writer.add(parse_line(raw))
                    except ParseError as exc:
                        await _dead_letter(raw.rstrip("\n"), str(exc))
                offset = fh.tell()
            _save_state(state_file, {log_file: offset})

        while True:
            try:
                event_type, path = await asyncio.wait_for(queue.get(), timeout=writer._interval)
            except asyncio.TimeoutError:
                # Flush on timeout even if no event
                await writer.flush()
                continue

            if str(path) != log_file:
                continue

            if event_type == "created":
                # Log rotation: file was recreated
                logger.info("Log rotation detected for %s; resetting offset", log_file)
                offset = 0

            if not os.path.exists(log_file):
                continue

            with open(log_file, "r", errors="replace") as fh:
                fh.seek(offset)
                for raw in fh:
                    if not raw.endswith("\n"):
                        break   # partial last line — wait for more data
                    try:
                        await writer.add(parse_line(raw))
                    except ParseError as exc:
                        await _dead_letter(raw.rstrip("\n"), str(exc))
                offset = fh.tell()

            _save_state(state_file, {log_file: offset})

    finally:
        observer.stop()
        observer.join()
        await writer.flush()


# ---------------------------------------------------------------------------
# Backfill mode
# ---------------------------------------------------------------------------

async def _backfill_file(log_file: str, writer: BatchWriter, pool: asyncpg.Pool) -> None:
    """Ingest *log_file* from beginning to end as fast as possible."""
    logger.info("Backfilling %s ...", log_file)
    count = 0

    async def _dead_letter(raw: str, err: str) -> None:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO dead_letter (raw_line, error) VALUES ($1, $2)",
                raw, err,
            )

    with open(log_file, "r", errors="replace") as fh:
        for raw in fh:
            try:
                await writer.add(parse_line(raw))
            except ParseError as exc:
                await _dead_letter(raw.rstrip("\n"), str(exc))
            count += 1

    await writer.flush()
    async with pool.acquire() as conn:
        await conn.execute("SELECT refresh_log_counts(NOW() - INTERVAL '30 days', NOW() + INTERVAL '1 hour')")
    logger.info("Backfill complete: %d lines processed", count)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _async_main(backfill: bool, log_file: str) -> None:
    cfg = get_config()
    log_file = log_file or cfg.log_file

    pool = await asyncpg.create_pool(
        cfg.postgres_dsn,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )

    es = AsyncElasticsearch(cfg.es_host)

    # Ensure ES index exists
    from ingest._es_setup import ensure_index
    await ensure_index(es)

    # Provision partitions at startup
    async with pool.acquire() as conn:
        await conn.execute("SELECT create_partitions(7)")
    logger.info("Initial partition provisioning complete")

    writer = BatchWriter(
        pg_pool=pool,
        es_client=es,
        batch_size=cfg.batch_size,
        flush_interval=cfg.flush_interval,
    )

    shutdown = asyncio.Event()

    def _handle_signal(sig: int, _frame: object) -> None:
        logger.info("Received signal %s; shutting down", sig)
        shutdown.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _handle_signal)

    try:
        if backfill:
            await _backfill_file(log_file, writer, pool)
        else:
            tasks = [
                asyncio.create_task(_tail_file(log_file, writer, pool, cfg.state_file)),
                asyncio.create_task(_maintain_partitions(pool)),
                asyncio.create_task(_maintain_rollup(pool)),
            ]
            await shutdown.wait()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await writer.close()
        await es.close()
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Log Analytics — ingest agent")
    parser.add_argument("--backfill", action="store_true", help="Backfill mode: read entire file")
    parser.add_argument("--file", default="", help="Override log file path")
    args = parser.parse_args()
    asyncio.run(_async_main(backfill=args.backfill, log_file=args.file))


if __name__ == "__main__":
    main()
