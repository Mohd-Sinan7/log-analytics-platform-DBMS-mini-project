"""
bench_ingest.py — Ingest throughput benchmark.

Generates N log lines in memory and times how fast they can be:
  1. Parsed
  2. Written to Postgres via COPY

Usage:
  python bench/bench_ingest.py --rows 100000
"""
from __future__ import annotations

import argparse
import asyncio
import io
import os
import sys
import time
import uuid
from datetime import datetime, timezone

import asyncpg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generator.generate_logs import make_line
from ingest.parser import parse_line, ParseError


def _pg_dsn() -> str:
    host     = os.environ.get("POSTGRES_HOST", "localhost")
    port     = os.environ.get("POSTGRES_PORT", "5432")
    db       = os.environ.get("POSTGRES_DB", "logs")
    user     = os.environ.get("POSTGRES_USER", "logs")
    password = os.environ.get("POSTGRES_PASSWORD", "logspassword")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def bench_parse(n: int) -> float:
    """Return parse throughput (lines/sec)."""
    now = datetime.now(tz=timezone.utc)
    lines = [make_line(now) for _ in range(n)]
    t0 = time.perf_counter()
    for line in lines:
        try:
            parse_line(line)
        except ParseError:
            pass
    elapsed = time.perf_counter() - t0
    return n / elapsed


async def bench_pg_copy(pool: asyncpg.Pool, n: int) -> float:
    """Bulk-insert n rows via COPY and return rows/sec."""
    now = datetime.now(tz=timezone.utc)
    lines = [make_line(now) for _ in range(n)]
    records = []
    for line in lines:
        try:
            records.append(parse_line(line))
        except ParseError:
            pass

    rows = [
        (uuid.uuid4(), rec.ts, rec.severity, rec.service, rec.host, rec.trace_id, rec.message)
        for rec in records
    ]

    t0 = time.perf_counter()
    async with pool.acquire() as conn:
        await conn.copy_records_to_table(
            "logs",
            records=rows,
            columns=["doc_id", "ts", "severity", "service", "host", "trace_id", "message"],
        )
    elapsed = time.perf_counter() - t0
    return len(records) / elapsed


async def main(n: int) -> None:
    print(f"\n=== Ingest Benchmark ({n:,} rows) ===\n")

    parse_rate = await bench_parse(n)
    print(f"Parse throughput:       {parse_rate:>10,.0f} lines/sec")

    pool = await asyncpg.create_pool(_pg_dsn(), min_size=2, max_size=5)
    pg_rate = await bench_pg_copy(pool, n)
    print(f"Postgres COPY:          {pg_rate:>10,.0f} rows/sec")
    await pool.close()

    # Append to BENCHMARKS.md
    md_path = os.path.join(os.path.dirname(__file__), "..", "docs", "BENCHMARKS.md")
    with open(md_path, "a") as f:
        f.write(f"\n## Ingest Benchmarks ({n:,} rows)\n\n")
        f.write("| Operation | Throughput |\n")
        f.write("|-----------|------------|\n")
        f.write(f"| Parse     | {parse_rate:,.0f} lines/sec |\n")
        f.write(f"| PG COPY   | {pg_rate:,.0f} rows/sec |\n")
    print(f"\nAppended to {md_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100_000)
    args = parser.parse_args()
    asyncio.run(main(args.rows))
