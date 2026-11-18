"""
detector.py — Z-score anomaly detector for the Log Analytics Platform.

Every *ANOMALY_INTERVAL* seconds, for each service:
  1. Fetch the error count in the latest completed minute bucket.
  2. Fetch the rolling mean and std of the previous 60 completed minute buckets.
  3. Compute z-score = (value - mean) / std.
  4. If z-score > threshold AND count >= min_count: insert into anomalies (idempotent).
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
import signal

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("anomaly.detector")

SERVICES = ["payments", "auth", "orders", "inventory", "search", "notifications"]
_ROLLUP_MINUTES = 60   # baseline window
_MIN_BASELINE   = 5    # need at least this many baseline buckets


def _pg_dsn() -> str:
    host     = os.environ.get("POSTGRES_HOST", "localhost")
    port     = os.environ.get("POSTGRES_PORT", "5432")
    db       = os.environ.get("POSTGRES_DB", "logs")
    user     = os.environ.get("POSTGRES_USER", "logs")
    password = os.environ.get("POSTGRES_PASSWORD", "logspassword")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def _detect_once(
    pool: asyncpg.Pool,
    zscore_threshold: float,
    min_count: int,
    bucket: object = None,
) -> None:
    """Run one anomaly detection pass across all services."""
    async with pool.acquire() as conn:
        # Latest completed minute bucket (or explicit bucket if provided)
        if bucket is None:
            latest_bucket = await conn.fetchval(
                """
                SELECT date_trunc('minute', NOW() - INTERVAL '1 minute')
                """
            )
        else:
            latest_bucket = bucket

        for service in SERVICES:
            # Current error count for the latest completed minute
            current = await conn.fetchval(
                """
                SELECT COALESCE(SUM(count), 0)
                FROM log_counts_minute
                WHERE bucket = $1
                  AND service = $2
                  AND severity IN ('ERROR', 'FATAL')
                """,
                latest_bucket, service,
            )

            # Baseline: previous 60 minutes (excluding latest_bucket)
            baseline_rows = await conn.fetch(
                """
                SELECT SUM(CASE WHEN severity IN ('ERROR','FATAL') THEN count ELSE 0 END) AS errors
                FROM log_counts_minute
                WHERE bucket >= ($1::timestamptz - INTERVAL '60 minutes')
                  AND bucket < $1::timestamptz
                  AND service = $2
                GROUP BY bucket
                ORDER BY bucket
                """,
                latest_bucket, service,
            )

            values = [float(r["errors"]) for r in baseline_rows]
            if len(values) < _MIN_BASELINE:
                logger.debug(
                    "Service %s: only %d baseline buckets; skipping", service, len(values)
                )
                continue

            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            std = math.sqrt(variance)

            if std < 1e-6:
                # No variance in baseline; skip to avoid div-by-zero
                continue

            value = float(current)
            zscore = (value - mean) / std

            logger.info(
                "Service %s: bucket=%s value=%.1f mean=%.2f std=%.2f zscore=%.2f (threshold=%.1f)",
                service, latest_bucket, value, mean, std, zscore, zscore_threshold,
            )

            if zscore > zscore_threshold and value >= min_count:
                try:
                    await conn.execute(
                        """
                        INSERT INTO anomalies
                            (bucket, service, metric, value, baseline_mean, baseline_std, zscore)
                        VALUES ($1, $2, 'error_count', $3, $4, $5, $6)
                        ON CONFLICT (bucket, service, metric) DO NOTHING
                        """,
                        latest_bucket, service, value, mean, std, zscore,
                    )
                    logger.warning(
                        "ANOMALY detected: service=%s bucket=%s zscore=%.2f value=%.0f",
                        service, latest_bucket, zscore, value,
                    )
                except Exception as exc:
                    logger.error("Failed to insert anomaly: %s", exc)


async def _main() -> None:
    interval       = int(os.environ.get("ANOMALY_INTERVAL", "60"))
    zscore_threshold = float(os.environ.get("ANOMALY_ZSCORE_THRESHOLD", "3.0"))
    min_count      = int(os.environ.get("ANOMALY_MIN_COUNT", "5"))

    pool = await asyncpg.create_pool(_pg_dsn(), min_size=1, max_size=3)
    logger.info(
        "Anomaly detector started: interval=%ds zscore_threshold=%.1f min_count=%d",
        interval, zscore_threshold, min_count,
    )

    shutdown = asyncio.Event()

    def _handle_signal(sig: int, _frame: object) -> None:
        logger.info("Received signal %s; shutting down", sig)
        shutdown.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _handle_signal)

    while not shutdown.is_set():
        try:
            await _detect_once(pool, zscore_threshold, min_count)
        except Exception as exc:
            logger.error("Detection cycle error: %s", exc)
        try:
            await asyncio.wait_for(shutdown.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass

    await pool.close()
    logger.info("Anomaly detector stopped")


if __name__ == "__main__":
    asyncio.run(_main())
